"""Education pathways (14_EDUCATION_MODEL.md §4, §5, §17, §18, §19).

An Education Pathway is a reusable, versioned graph describing a route to
competence. It is reusable across careers (INV-01), keeps country-specific
information modular (§25), and references subjects/skills rather than embedding
them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.identifiers import (
    EducationPathwayId,
    InstitutionId,
    QualificationId,
    SubjectId,
)
from ..common.scores import UnitInterval
from ..common.versioning import Version
from .competencies import EducationSkill, LearningOutcome
from .enums import EducationLevel, PathwayKind


@dataclass(frozen=True, slots=True)
class GeographicContext:
    """Localized context for a pathway (14 §17). Kept modular by design."""

    country: str = ""
    region: str = ""
    education_system: str = ""
    qualification_framework: str = ""
    language: str = ""


@dataclass(frozen=True, slots=True)
class FinancialEstimate:
    """Financial information for a pathway (14 §18). Versioned upstream."""

    currency: str = ""
    estimated_total_cost: float | None = None
    tuition: float | None = None
    living_expenses: float | None = None
    scholarships_available: bool | None = None
    expected_roi: UnitInterval | None = None


@dataclass(frozen=True, slots=True)
class TimeEstimate:
    """Duration characteristics of a pathway (14 §19)."""

    typical_months: int | None = None
    minimum_months: int | None = None
    maximum_months: int | None = None
    flexible_pace: bool | None = None

    def __post_init__(self) -> None:
        lo, hi = self.minimum_months, self.maximum_months
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("minimum_months cannot exceed maximum_months")


@dataclass(frozen=True, slots=True)
class SubjectComponent:
    """A subject within a pathway with relationship metadata (14 §10)."""

    subject_id: SubjectId
    importance: str = ""
    depth: str = ""
    sequence: int | None = None
    credits: int | None = None


@dataclass(frozen=True, slots=True)
class EducationPathway:
    """A reusable, versioned route to acquiring competencies."""

    id: EducationPathwayId
    name: str
    kind: PathwayKind
    version: Version
    level: EducationLevel | None = None
    qualifications: tuple[QualificationId, ...] = field(default_factory=tuple)
    subjects: tuple[SubjectComponent, ...] = field(default_factory=tuple)
    skills: tuple[EducationSkill, ...] = field(default_factory=tuple)
    outcomes: tuple[LearningOutcome, ...] = field(default_factory=tuple)
    institutions: tuple[InstitutionId, ...] = field(default_factory=tuple)
    prerequisites: tuple[EducationPathwayId, ...] = field(default_factory=tuple)
    geography: GeographicContext = field(default_factory=GeographicContext)
    cost: FinancialEstimate = field(default_factory=FinancialEstimate)
    duration: TimeEstimate = field(default_factory=TimeEstimate)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("EducationPathway.name must be non-empty")
