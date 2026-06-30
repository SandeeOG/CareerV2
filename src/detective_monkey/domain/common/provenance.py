"""Provenance.

"Nothing should be untraceable" (18 §13). Every derived output must be able to
answer *where did this come from?* Provenance records the source, the data
origin, and references back to the evidence or external sources that produced a
value (00 §15 Data Integrity, 11 §18 "store provenance for every derived
feature").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    """Where a piece of information originated (11 §7, 13 §11, 15 §24, 19 §14)."""

    ASSESSMENT = "assessment"
    ACADEMIC_RECORD = "academic_record"
    CERTIFICATION = "certification"
    PROJECT = "project"
    COMPETITION = "competition"
    PORTFOLIO = "portfolio"
    INTERVIEW = "interview"
    TEACHER_VALIDATION = "teacher_validation"
    PEER_VALIDATION = "peer_validation"
    SELF_REPORT = "self_report"
    EXTERNAL_INTEGRATION = "external_integration"
    GOVERNMENT_STATISTICS = "government_statistics"
    INDUSTRY_REPORT = "industry_report"
    JOB_BOARD = "job_board"
    RESEARCH = "research"
    DERIVED = "derived"  # produced deterministically from other domain objects
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Provenance:
    """An immutable record of the origin of a value.

    ``references`` are opaque identifiers (e.g. evidence ids, external dataset
    URIs) so the domain stays decoupled from any storage layer.
    """

    source: SourceType
    description: str = ""
    references: tuple[str, ...] = field(default_factory=tuple)
    recorded_at: datetime = field(default_factory=_utcnow)

    def with_reference(self, reference: str) -> "Provenance":
        return Provenance(
            source=self.source,
            description=self.description,
            references=self.references + (reference,),
            recorded_at=self.recorded_at,
        )
