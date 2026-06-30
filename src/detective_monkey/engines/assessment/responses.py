"""Assessment responses and results (21_ASSESSMENT_ENGINE.md §5, §15, §20).

Responses carry timing (21 §15), which becomes evidence and never gets ignored.
The engine's output is an evidence package — no Student Profile is generated here
(21 §5, INV-06).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.evidence import Evidence
from ...domain.common.identifiers import StudentId
from ...domain.common.versioning import Version


@dataclass(frozen=True, slots=True)
class ItemResponse:
    """A single response with timing (21 §15)."""

    question_id: str
    value: float | None = None  # None = missing (never fabricated)
    duration_ms: int | None = None
    review_count: int = 0


@dataclass(frozen=True, slots=True)
class AssessmentSubmission:
    """A student's responses to one assessment version (21 §4)."""

    student_id: StudentId
    definition_id: str
    definition_version: Version
    responses: tuple[ItemResponse, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QualityMetrics:
    """Response-quality signals (21 §13). All in [0, 1] where applicable."""

    completion: float
    straight_lining: float
    speeding: float
    mean_duration_ms: float | None = None


@dataclass(frozen=True, slots=True)
class AssessmentResult:
    """The engine output: an evidence package plus quality/timing (21 §20)."""

    student_id: StudentId
    definition_id: str
    definition_version: Version
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    quality: QualityMetrics | None = None
