"""CareerSkill — a career's requirement for a skill (13_SKILLS_MODEL.md §14).

Like ``StudentSkill``, a ``CareerSkill`` references a canonical ``Skill`` rather
than embedding it. The Recommendation Engine compares ``StudentSkill`` against
``CareerSkill`` (13 §14); a career requirement never modifies a student skill
(INV-05).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.identifiers import CareerId, SkillId
from ..common.scores import Importance, ProficiencyLevel, UnitInterval


@dataclass(frozen=True, slots=True)
class CareerSkill:
    """An immutable description of how a skill matters to a career."""

    career_id: CareerId
    skill_id: SkillId
    importance: Importance
    minimum_proficiency: ProficiencyLevel
    recommended_proficiency: ProficiencyLevel
    future_importance: UnitInterval | None = None
    market_demand: UnitInterval | None = None
    criticality: Importance | None = None

    def __post_init__(self) -> None:
        if self.recommended_proficiency.value < self.minimum_proficiency.value:
            raise ValueError(
                "recommended_proficiency cannot be lower than minimum_proficiency"
            )
