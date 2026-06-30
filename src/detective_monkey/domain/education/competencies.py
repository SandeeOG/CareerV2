"""Competencies and learning outcomes (14_EDUCATION_MODEL.md §11, §12, §13).

A competency is an integrated capability built from multiple skills (14 §12).
``EducationSkill`` links a pathway to the skills it develops (14 §11), keeping
skills reusable rather than embedded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.identifiers import CompetencyId, SkillId
from ..common.scores import Importance, ProficiencyLevel
from ..common.versioning import Version


@dataclass(frozen=True, slots=True)
class Competency:
    """An integrated capability composed of multiple skills (14 §12)."""

    id: CompetencyId
    name: str
    version: Version
    skill_set: tuple[SkillId, ...] = field(default_factory=tuple)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Competency.name must be non-empty")


@dataclass(frozen=True, slots=True)
class EducationSkill:
    """The relationship between a pathway and a skill it develops (14 §11)."""

    skill_id: SkillId
    expected_proficiency: ProficiencyLevel
    importance: Importance
    assessment_method: str = ""
    evidence_type: str = ""


@dataclass(frozen=True, slots=True)
class LearningOutcome:
    """A measurable outcome of a pathway (14 §13)."""

    description: str
    competency_id: CompetencyId | None = None

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("LearningOutcome.description must be non-empty")
