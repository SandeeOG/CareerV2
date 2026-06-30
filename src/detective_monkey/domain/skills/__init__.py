"""Skills Model (13_SKILLS_MODEL.md).

Skills are reusable, versioned, evidence-backed graph entities that bridge the
Student Intelligence Model and the Career Intelligence Model. ``Skill`` is the
canonical entity; ``StudentSkill`` and ``CareerSkill`` are separate relationship
objects so a skill is never duplicated.
"""

from .career_skill import CareerSkill
from .relationships import SkillRelationship
from .skill import (
    Skill,
    SkillClassification,
    SkillLearningProfile,
    SkillMarketProfile,
)
from .skill_gap import SkillGap
from .student_skill import StudentSkill
from .taxonomy import SkillCategory, SkillLifecycle, SkillRelationType

__all__ = [
    "Skill",
    "SkillClassification",
    "SkillLearningProfile",
    "SkillMarketProfile",
    "SkillRelationship",
    "StudentSkill",
    "CareerSkill",
    "SkillGap",
    "SkillCategory",
    "SkillRelationType",
    "SkillLifecycle",
]
