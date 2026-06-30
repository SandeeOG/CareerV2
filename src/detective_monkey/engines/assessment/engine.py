"""Assessment Engine (21_ASSESSMENT_ENGINE.md).

Transforms structured responses into validated, standardized evidence. It owns
the assessment lifecycle but not interpretation: it produces evidence only and
never generates recommendations or profiles (INV-06). Construct mapping is
deterministic (INV-05) and evidence is reproducible (INV-04) — evidence ids are
derived from the inputs rather than randomly generated.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...contracts import (
    BaseEngine,
    EngineError,
    EngineErrorType,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    EngineStatus,
    IntelligenceLayer,
)
from ...domain.common.attributes import Attributes
from ...domain.common.confidence import Confidence, ConfidenceFactor
from ...domain.common.events import DomainEvent, EventName
from ...domain.common.evidence import Evidence
from ...domain.common.identifiers import EvidenceId
from ...domain.common.provenance import Provenance, SourceType
from ...domain.common.scores import UnitInterval
from ...domain.common.versioning import Version
from .definitions import AssessmentDefinition, MissingPolicy, Question
from .responses import (
    AssessmentResult,
    AssessmentSubmission,
    ItemResponse,
    QualityMetrics,
)

ENGINE_VERSION = Version(1, "P2")
_DEFAULT_SPEEDING_MS = 800.0


@dataclass(frozen=True, slots=True)
class AssessmentInput:
    """Engine payload: a definition plus a submission (21 §4)."""

    definition: AssessmentDefinition
    submission: AssessmentSubmission


class AssessmentEngine(BaseEngine[AssessmentInput, AssessmentResult]):
    """Deterministic measurement engine (21 §1)."""

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="assessment_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.EVIDENCE,
            description="Transforms assessment responses into validated evidence.",
        )

    def validate(self, request: EngineRequest[AssessmentInput]) -> list[EngineError]:
        defn = request.payload.definition
        sub = request.payload.submission
        errors: list[EngineError] = []

        if sub.definition_id != defn.id or sub.definition_version != defn.version:
            errors.append(
                EngineError(
                    EngineErrorType.CONFIGURATION,
                    "definition_mismatch",
                    "Submission references a different assessment definition/version "
                    "(21 INV-08).",
                )
            )
            return errors  # cannot proceed against the wrong definition

        valid_ids = defn.question_ids()
        seen: set[str] = set()
        by_id = {q.id: q for q in defn.questions()}
        for r in sub.responses:
            if r.question_id not in valid_ids:
                errors.append(
                    EngineError(
                        EngineErrorType.VALIDATION,
                        "unknown_question",
                        f"Response references unknown question '{r.question_id}'.",
                    )
                )
                continue
            if r.question_id in seen:
                errors.append(
                    EngineError(
                        EngineErrorType.VALIDATION,
                        "duplicate_response",
                        f"Duplicate response for question '{r.question_id}'.",
                    )
                )
            seen.add(r.question_id)
            q = by_id[r.question_id]
            if r.value is not None and not (q.scale_min <= r.value <= q.scale_max):
                errors.append(
                    EngineError(
                        EngineErrorType.VALIDATION,
                        "value_out_of_range",
                        f"Response to '{r.question_id}' is outside its scale.",
                    )
                )

        if defn.missing_policy is MissingPolicy.REJECT:
            answered = {r.question_id for r in sub.responses if r.value is not None}
            if answered != valid_ids:
                errors.append(
                    EngineError(
                        EngineErrorType.VALIDATION,
                        "incomplete_assessment",
                        "Missing responses are not permitted under REJECT policy.",
                    )
                )
        return errors

    def _run(
        self, request: EngineRequest[AssessmentInput]
    ) -> EngineOutcome[AssessmentResult]:
        defn = request.payload.definition
        sub = request.payload.submission
        by_id = {q.id: q for q in defn.questions()}
        answered = [r for r in sub.responses if r.value is not None]

        quality = self._quality(defn, sub, answered, request.configuration)

        # Aggregate normalized item scores per construct.
        per_construct: dict[str, list[tuple[float, float]]] = {}  # value, weight
        for r in answered:
            q = by_id[r.question_id]
            per_construct.setdefault(q.construct, []).append(
                (self._normalize(q, r.value), q.weight)  # type: ignore[arg-type]
            )

        evidence: list[Evidence] = []
        construct_confidences: list[float] = []
        for construct, pairs in sorted(per_construct.items()):
            total_w = sum(w for _, w in pairs)
            score = sum(v * w for v, w in pairs) / total_w if total_w else 0.0
            conf = self._construct_confidence(len(pairs), quality)
            construct_confidences.append(conf)
            evidence.append(
                Evidence(
                    id=self._evidence_id(sub, construct),
                    subject=construct,
                    provenance=Provenance(
                        SourceType.ASSESSMENT,
                        description=f"Assessment {defn.id} {defn.version}",
                        references=(defn.id,),
                    ),
                    confidence=Confidence.of(
                        conf,
                        ConfidenceFactor("item_count", UnitInterval(min(1.0, len(pairs) / 3)),
                                         "Number of items measuring this construct"),
                    ),
                    summary=f"Measured construct '{construct}' = {score:.1f}/100",
                    metadata=Attributes.of(
                        value=f"{score:.4f}",
                        item_count=str(len(pairs)),
                        kind="construct_observation",
                    ),
                )
            )

        # A separate evidence object capturing response quality (21 §13).
        evidence.append(
            Evidence(
                id=self._evidence_id(sub, "response_quality"),
                subject="response_quality",
                provenance=Provenance(SourceType.ASSESSMENT, references=(defn.id,)),
                confidence=Confidence.of(1.0),
                summary="Response-quality signals for this assessment.",
                metadata=Attributes.of(
                    completion=f"{quality.completion:.4f}",
                    straight_lining=f"{quality.straight_lining:.4f}",
                    speeding=f"{quality.speeding:.4f}",
                    kind="quality_observation",
                ),
            )
        )

        result = AssessmentResult(
            student_id=sub.student_id,
            definition_id=defn.id,
            definition_version=defn.version,
            evidence=tuple(evidence),
            quality=quality,
        )

        overall = (
            sum(construct_confidences) / len(construct_confidences)
            if construct_confidences
            else 0.0
        )
        status = (
            EngineStatus.PARTIAL if quality.completion < 1.0 else EngineStatus.SUCCESS
        )
        warnings = (
            ["Assessment is incomplete; downstream confidence will be reduced."]
            if quality.completion < 1.0
            else []
        )
        events = [
            DomainEvent(EventName.ASSESSMENT_COMPLETED, str(sub.student_id),
                        correlation_id=request.context.correlation_id),
            DomainEvent(EventName.EVIDENCE_COLLECTED, str(sub.student_id),
                        correlation_id=request.context.correlation_id),
        ]
        return EngineOutcome(
            result=result,
            status=status,
            confidence=Confidence.of(overall),
            provenance=Provenance(SourceType.ASSESSMENT, references=(defn.id,)),
            events=events,
            warnings=warnings,
            metrics={"constructs": str(len(per_construct)),
                     "evidence": str(len(evidence))},
        )

    # -- deterministic helpers --------------------------------------------

    @staticmethod
    def _normalize(q: Question, value: float) -> float:
        """Apply reverse scoring (21 §11) and normalize to [0, 100]."""
        used = (q.scale_max + q.scale_min - value) if q.reverse_scored else value
        return (used - q.scale_min) / (q.scale_max - q.scale_min) * 100.0

    @staticmethod
    def _construct_confidence(n_items: int, quality: QualityMetrics) -> float:
        item_factor = min(1.0, n_items / 3.0)
        quality_factor = (1.0 - quality.straight_lining) * (1.0 - quality.speeding)
        return max(0.0, min(1.0, 0.3 + 0.7 * item_factor * quality_factor))

    @staticmethod
    def _quality(
        defn: AssessmentDefinition,
        sub: AssessmentSubmission,
        answered: list[ItemResponse],
        config: Attributes,
    ) -> QualityMetrics:
        total = len(defn.questions())
        completion = (len(answered) / total) if total else 0.0

        # Straight-lining: share of answered items equal to the modal value.
        if answered:
            counts: dict[float, int] = {}
            for r in answered:
                counts[r.value] = counts.get(r.value, 0) + 1  # type: ignore[index]
            straight = max(counts.values()) / len(answered)
        else:
            straight = 0.0

        threshold = float(config.get("speeding_threshold_ms") or _DEFAULT_SPEEDING_MS)
        timed = [r for r in answered if r.duration_ms is not None]
        if timed:
            sped = sum(1 for r in timed if r.duration_ms < threshold)  # type: ignore[operator]
            speeding = sped / len(timed)
            mean_duration = sum(r.duration_ms for r in timed) / len(timed)  # type: ignore[misc]
        else:
            speeding = 0.0
            mean_duration = None

        return QualityMetrics(
            completion=completion,
            straight_lining=straight,
            speeding=speeding,
            mean_duration_ms=mean_duration,
        )

    @staticmethod
    def _evidence_id(sub: AssessmentSubmission, subject: str) -> EvidenceId:
        # Deterministic id => reproducible evidence (21 INV-04).
        return EvidenceId(
            f"evidence_{sub.student_id}_{sub.definition_id}_v{sub.definition_version.number}_{subject}"
        )
