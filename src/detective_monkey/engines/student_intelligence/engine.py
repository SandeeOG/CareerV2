"""Student Intelligence Engine (23_STUDENT_INTELLIGENCE_ENGINE.md).

Transforms validated evidence and engineered features into the canonical,
immutable Student Intelligence Profile. Deterministic (INV-08); consumes only
canonical objects, never raw assessments (INV-06); never calls LLMs (INV-07);
never generates recommendations (§1). Missing information is explicit, never
fabricated (§12, 11 INV-08), and profile generation degrades gracefully (§21).
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
from ...domain.common.confidence import Confidence
from ...domain.common.identifiers import ProfileId, StudentId
from ...domain.common.provenance import Provenance, SourceType
from ...domain.common.scores import Score, UnitInterval
from ...domain.common.versioning import Version, VersionSet
from ...domain.common.events import DomainEvent, EventName
from ...domain.student.profile import ProfileStatus, StudentIntelligenceProfile
from ...domain.student.reliability import ReliabilityMetrics
from ...domain.student.scores import ConstructScore, DerivedFeature, DomainScore
from ..evidence.graph import EvidenceGraph
from ..feature_engineering.store import FeatureSet
from .config import ReasoningConfig

ENGINE_VERSION = Version(1, "P2")


@dataclass(frozen=True, slots=True)
class StudentIntelligenceInput:
    """Engine payload (23 §17)."""

    student_id: StudentId
    evidence_graph: EvidenceGraph
    feature_set: FeatureSet
    config: ReasoningConfig
    profile_version: Version = Version(1)


class StudentIntelligenceEngine(
    BaseEngine[StudentIntelligenceInput, StudentIntelligenceProfile]
):
    """Deterministic reasoning over evidence + features (23 §1)."""

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="student_intelligence_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.INFERENCE,
            description="Builds the canonical Student Intelligence Profile.",
        )

    def validate(
        self, request: EngineRequest[StudentIntelligenceInput]
    ) -> list[EngineError]:
        payload = request.payload
        errors: list[EngineError] = []
        if payload.feature_set.student_id != payload.student_id:
            errors.append(
                EngineError(EngineErrorType.VALIDATION, "student_mismatch",
                            "Feature set belongs to a different student.")
            )
        if payload.evidence_graph.student_id != payload.student_id:
            errors.append(
                EngineError(EngineErrorType.VALIDATION, "student_mismatch",
                            "Evidence graph belongs to a different student.")
            )
        return errors

    def _run(
        self, request: EngineRequest[StudentIntelligenceInput]
    ) -> EngineOutcome[StudentIntelligenceProfile]:
        payload = request.payload
        cfg = payload.config
        features = payload.feature_set

        # 1. Construct reasoning: each construct comes from a feature (INV-03).
        construct_scores: list[ConstructScore] = []
        construct_index: dict[str, ConstructScore] = {}
        missing_constructs: list[str] = []
        for src in cfg.construct_sources:
            fv = features.by_id(src.feature_id)
            if fv is None:
                missing_constructs.append(src.construct)  # unknown, not fabricated
                continue
            cs = ConstructScore(
                construct=src.construct,
                score=Score(self._clamp_100(fv.value)),
                confidence=fv.confidence,
                evidence=fv.sources,
                provenance=Provenance(SourceType.DERIVED, references=(src.feature_id,)),
            )
            construct_scores.append(cs)
            construct_index[src.construct] = cs

        # 2. Domain aggregation (configurable, INV — no hardcoded rules).
        domain_scores: list[DomainScore] = []
        for rule in cfg.domain_rules:
            present = [(c, w) for c, w in rule.components if c in construct_index]
            if not present:
                continue
            total_w = sum(w for _, w in present)
            value = sum(construct_index[c].score.value * w for c, w in present) / total_w
            conf = min(construct_index[c].confidence.value.value for c, _ in present)
            domain_scores.append(
                DomainScore(
                    domain=rule.domain,
                    score=Score(self._clamp_100(value)),
                    confidence=Confidence.of(conf),
                    derived_from=tuple(c for c, _ in present),
                )
            )

        # 3. Derived features (must reference evidence, INV-03).
        derived: list[DerivedFeature] = []
        for spec in cfg.derived_features:
            fv = features.by_id(spec.feature_id)
            if fv is None or not fv.sources:
                continue  # skip rather than fabricate / violate INV-03
            derived.append(
                DerivedFeature(
                    name=spec.name,
                    score=Score(self._clamp_100(fv.value)),
                    confidence=fv.confidence,
                    evidence=fv.sources,
                    provenance=Provenance(SourceType.DERIVED, references=(spec.feature_id,)),
                )
            )

        reliability = self._reliability(
            n_present=len(construct_scores),
            n_expected=len(cfg.construct_sources),
            n_conflicts=len(payload.evidence_graph.conflicts),
            construct_scores=construct_scores,
        )

        evidence_ids = tuple(
            sorted({eid for cs in construct_scores for eid in cs.evidence},
                   key=lambda e: e.value)
        )
        input_versions = (
            VersionSet()
            .with_ref("feature_engine", Version(1))
            .with_ref("engine", ENGINE_VERSION)
            .with_ref("reasoning_config", cfg.version)
        )
        profile = StudentIntelligenceProfile(
            id=ProfileId(f"profile_{payload.student_id}_v{payload.profile_version.number}"),
            student_id=payload.student_id,
            profile_version=payload.profile_version,
            construct_scores=tuple(construct_scores),
            domain_scores=tuple(domain_scores),
            derived_features=tuple(derived),
            reliability=reliability,
            evidence=evidence_ids,
            input_versions=input_versions,
            provenance=Provenance(SourceType.DERIVED),
            status=ProfileStatus.ACTIVE,
        )

        completeness = (
            len(construct_scores) / len(cfg.construct_sources)
            if cfg.construct_sources
            else 0.0
        )
        status = EngineStatus.PARTIAL if completeness < 1.0 else EngineStatus.SUCCESS
        warnings: list[str] = []
        if missing_constructs:
            warnings.append(
                "Insufficient evidence for constructs: "
                + ", ".join(sorted(missing_constructs))
                + " (recorded as unknown, 23 §12)."
            )
        overall = (
            sum(cs.confidence.value.value for cs in construct_scores) / len(construct_scores)
            if construct_scores
            else 0.0
        )
        return EngineOutcome(
            result=profile,
            status=status,
            confidence=Confidence.of(overall),
            provenance=Provenance(SourceType.DERIVED),
            events=[DomainEvent(EventName.STUDENT_PROFILE_GENERATED,
                                str(payload.student_id),
                                correlation_id=request.context.correlation_id)],
            warnings=warnings,
            metrics={
                "constructs": str(len(construct_scores)),
                "domains": str(len(domain_scores)),
                "derived_features": str(len(derived)),
                "completeness": f"{completeness:.3f}",
            },
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _clamp_100(value: float) -> float:
        return max(0.0, min(100.0, value))

    @staticmethod
    def _reliability(
        n_present: int,
        n_expected: int,
        n_conflicts: int,
        construct_scores: list[ConstructScore],
    ) -> ReliabilityMetrics:
        completeness = (n_present / n_expected) if n_expected else 0.0
        mean_conf = (
            sum(cs.confidence.value.value for cs in construct_scores) / len(construct_scores)
            if construct_scores
            else 0.0
        )
        # Each conflict modestly reduces internal consistency.
        consistency = max(0.0, 1.0 - 0.1 * n_conflicts)
        return ReliabilityMetrics(
            internal_consistency=UnitInterval(consistency),
            evidence_completeness=UnitInterval(completeness),
            missing_information=UnitInterval(1.0 - completeness),
            uncertainty=UnitInterval(max(0.0, 1.0 - mean_conf)),
        )
