"""SkillGap — a first-class domain object (13_SKILLS_MODEL.md §15, 16 §13).

A skill gap is the difference between what a career requires (``CareerSkill``)
and what a student currently demonstrates (``StudentSkill``). Gaps are computed
deterministically by the Recommendation Engine (Phase 2); the domain only
defines the object's shape. A gap never reduces explainability (16 §13).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.identifiers import SkillId
from ..common.scores import ProficiencyLevel


@dataclass(frozen=True, slots=True)
class SkillGap:
    """The proficiency shortfall for one skill relative to a career requirement."""

    skill_id: SkillId
    required_proficiency: ProficiencyLevel
    current_proficiency: ProficiencyLevel

    @property
    def gap_levels(self) -> int:
        """How many proficiency levels are missing (0 if already met)."""
        return max(0, self.required_proficiency.value - self.current_proficiency.value)

    @property
    def is_met(self) -> bool:
        return self.gap_levels == 0
