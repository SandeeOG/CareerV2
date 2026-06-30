"""StudentEducation and EducationGap (14_EDUCATION_MODEL.md §20, §21).

Student education is represented separately from canonical pathways (§25 DO NOT
"Mix student records with canonical education pathways"). The Education Gap is a
first-class object, distinct from a Skill Gap (14 §21).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..common.evidence import Evidence
from ..common.identifiers import (
    EducationPathwayId,
    InstitutionId,
    StudentId,
)
from .enums import EnrollmentStatus, RequirementType


@dataclass(frozen=True, slots=True)
class StudentEducation:
    """A student's record against a canonical education pathway."""

    student_id: StudentId
    pathway_id: EducationPathwayId
    status: EnrollmentStatus
    institution_id: InstitutionId | None = None
    grades: str = ""
    credits: int | None = None
    completion: float | None = None  # fraction complete in [0, 1]
    start_date: date | None = None
    end_date: date | None = None
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.completion is not None and not (0.0 <= self.completion <= 1.0):
            raise ValueError("completion must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class EducationGap:
    """The gap between current education and a career's required pathway."""

    pathway_id: EducationPathwayId
    requirement_type: RequirementType
    satisfied: bool

    @property
    def is_blocking(self) -> bool:
        """A mandatory, unsatisfied requirement blocks the career."""
        return self.requirement_type is RequirementType.MANDATORY and not self.satisfied
