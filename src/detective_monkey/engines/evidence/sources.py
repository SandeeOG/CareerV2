"""Raw observations and normalization (22_EVIDENCE_ENGINE.md §5, §11, §13).

Different sources produce different formats; the engine converts them all into
one canonical `Evidence` structure (§11). Source reliability drives the base
confidence (§13) and is configurable rather than hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...domain.common.identifiers import StudentId
from ...domain.common.provenance import SourceType
from .graph import EvidenceRelationType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Default base reliability per source (22 §13). Overridable via configuration.
DEFAULT_SOURCE_RELIABILITY: dict[SourceType, float] = {
    SourceType.ASSESSMENT: 0.80,
    SourceType.ACADEMIC_RECORD: 0.85,
    SourceType.CERTIFICATION: 0.90,
    SourceType.PROJECT: 0.70,
    SourceType.COMPETITION: 0.85,
    SourceType.PORTFOLIO: 0.65,
    SourceType.INTERVIEW: 0.70,
    SourceType.TEACHER_VALIDATION: 0.85,
    SourceType.PEER_VALIDATION: 0.60,
    SourceType.SELF_REPORT: 0.40,
    SourceType.EXTERNAL_INTEGRATION: 0.70,
    SourceType.GOVERNMENT_STATISTICS: 0.95,
    SourceType.INDUSTRY_REPORT: 0.80,
    SourceType.JOB_BOARD: 0.60,
    SourceType.RESEARCH: 0.85,
    SourceType.DERIVED: 0.75,
    SourceType.SYSTEM: 0.90,
}


@dataclass(frozen=True, slots=True)
class RawObservation:
    """A raw, un-normalized observation entering the Evidence Engine (22 §2).

    ``value`` is an optional measured magnitude (e.g. a normalized score); when
    present it participates in conflict detection. ``relation``/``target`` let an
    observation declare what entity it concerns (22 §17).
    """

    student_id: StudentId
    source: SourceType
    subject: str
    value: float | None = None
    verified: bool = False
    summary: str = ""
    relation: EvidenceRelationType | None = None
    target_subject: str = ""
    observed_at: datetime = field(default_factory=_utcnow)
    attributes: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("RawObservation.subject must be non-empty")
