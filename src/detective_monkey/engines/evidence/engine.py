"""Evidence Engine (22_EVIDENCE_ENGINE.md).

The gateway between data collection and intelligence. It normalizes
heterogeneous observations into canonical, immutable, traceable evidence
(INV-01, INV-02, INV-04), deduplicates, estimates confidence, stores conflicts
rather than discarding them (§14), and assembles the Evidence Graph. It performs
no interpretation and no recommendations (INV-06).
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
from ...domain.common.confidence import Confidence
from ...domain.common.events import DomainEvent, EventName
from ...domain.common.evidence import Evidence
from ...domain.common.identifiers import EvidenceId, StudentId
from ...domain.common.provenance import Provenance
from ...domain.common.versioning import Version
from .graph import (
    EvidenceConflict,
    EvidenceGraph,
    EvidenceRelation,
)
from .sources import DEFAULT_SOURCE_RELIABILITY, RawObservation

ENGINE_VERSION = Version(1, "P2")


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    """Engine payload (22 §20). Accepts raw observations and/or ready evidence
    (e.g. evidence already produced by the Assessment Engine)."""

    student_id: StudentId
    observations: tuple[RawObservation, ...] = field(default_factory=tuple)
    existing_evidence: tuple[Evidence, ...] = field(default_factory=tuple)


def evidence_value(ev: Evidence) -> float | None:
    """Read the numeric magnitude an evidence item carries, if any."""
    raw = ev.metadata.get("value")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class EvidenceEngine(BaseEngine[EvidenceInput, EvidenceGraph]):
    """Deterministic evidence normalization and graph construction (22 §1)."""

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="evidence_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.EVIDENCE,
            description="Normalizes observations into a canonical Evidence Graph.",
        )

    def validate(self, request: EngineRequest[EvidenceInput]) -> list[EngineError]:
        payload = request.payload
        errors: list[EngineError] = []
        for obs in payload.observations:
            if obs.student_id != payload.student_id:
                errors.append(
                    EngineError(
                        EngineErrorType.VALIDATION,
                        "student_mismatch",
                        f"Observation for '{obs.subject}' belongs to a different student.",
                    )
                )
        return errors

    def _run(self, request: EngineRequest[EvidenceInput]) -> EngineOutcome[EvidenceGraph]:
        payload = request.payload
        reliability = self._reliability(request.configuration)

        normalized = [self._normalize(obs, reliability) for obs in payload.observations]
        relations = [
            EvidenceRelation(self._obs_id(obs), obs.relation, obs.target_subject)
            for obs in payload.observations
            if obs.relation is not None and obs.target_subject
        ]

        # Combine with pre-formed evidence, then deduplicate by id.
        combined: dict[str, Evidence] = {}
        duplicates = 0
        for ev in (*payload.existing_evidence, *normalized):
            if ev.id.value in combined:
                duplicates += 1
                continue
            combined[ev.id.value] = ev
        evidence = tuple(sorted(combined.values(), key=lambda e: e.id.value))

        conflicts = self._detect_conflicts(evidence)

        graph = EvidenceGraph(
            student_id=payload.student_id,
            evidence=evidence,
            relations=tuple(relations),
            conflicts=tuple(conflicts),
        )

        overall = (
            sum(e.confidence.value.value for e in evidence) / len(evidence)
            if evidence
            else 0.0
        )
        warnings: list[str] = []
        if conflicts:
            warnings.append(
                f"{len(conflicts)} conflicting subject(s) preserved for downstream "
                "resolution (22 §14)."
            )
        events = [
            DomainEvent(EventName.EVIDENCE_COLLECTED, str(payload.student_id),
                        correlation_id=request.context.correlation_id),
        ]
        if relations:
            events.append(
                DomainEvent(EventName.KNOWLEDGE_LINKED, str(payload.student_id),
                            correlation_id=request.context.correlation_id)
            )
        return EngineOutcome(
            result=graph,
            confidence=Confidence.of(overall),
            events=events,
            warnings=warnings,
            metrics={
                "evidence": str(len(evidence)),
                "relations": str(len(relations)),
                "conflicts": str(len(conflicts)),
                "duplicates_removed": str(duplicates),
            },
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _reliability(config: Attributes) -> dict:
        table = dict(DEFAULT_SOURCE_RELIABILITY)
        for source in list(table):
            override = config.get(f"reliability:{source.value}")
            if override is not None:
                try:
                    table[source] = float(override)
                except ValueError:
                    pass
        return table

    def _normalize(self, obs: RawObservation, reliability: dict) -> Evidence:
        base = reliability.get(obs.source, 0.5)
        conf = min(1.0, base + 0.1) if obs.verified else base
        meta = {
            "kind": "observation",
            "verified": "true" if obs.verified else "false",
            **dict(obs.attributes),
        }
        if obs.value is not None:
            meta["value"] = f"{obs.value:.4f}"
        return Evidence(
            id=self._obs_id(obs),
            subject=obs.subject,
            provenance=Provenance(obs.source, description=obs.summary),
            confidence=Confidence.of(conf),
            summary=obs.summary or f"Observation about '{obs.subject}'.",
            observed_at=obs.observed_at,
            metadata=Attributes(tuple(meta.items())),
        )

    @staticmethod
    def _obs_id(obs: RawObservation) -> EvidenceId:
        val = "na" if obs.value is None else f"{obs.value:.4f}"
        return EvidenceId(f"evidence_{obs.student_id}_{obs.source.value}_{obs.subject}_{val}")

    @staticmethod
    def _detect_conflicts(evidence: tuple[Evidence, ...]) -> list[EvidenceConflict]:
        by_subject: dict[str, list[Evidence]] = {}
        for e in evidence:
            if evidence_value(e) is not None:
                by_subject.setdefault(e.subject, []).append(e)
        conflicts: list[EvidenceConflict] = []
        for subject, items in sorted(by_subject.items()):
            distinct = {round(evidence_value(e), 1) for e in items}  # type: ignore[arg-type]
            if len(distinct) > 1:
                conflicts.append(
                    EvidenceConflict(
                        subject=subject,
                        evidence_ids=tuple(e.id for e in items),
                        note=f"Disagreeing values: {sorted(distinct)}",
                    )
                )
        return conflicts
