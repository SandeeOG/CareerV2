"""Skill-to-skill relationships (13_SKILLS_MODEL.md §6, §7, §9).

Relationships are explicit (INV-03) and carry metadata; prerequisite trees are
never hardcoded (13 §23 DO NOT). Each relationship references reusable ``Skill``
ids rather than embedding skills.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.confidence import Confidence
from ..common.identifiers import EvidenceId, SkillId
from ..common.scores import UnitInterval
from ..common.versioning import Version
from .taxonomy import SkillRelationType


@dataclass(frozen=True, slots=True)
class SkillRelationship:
    """A directed, typed relationship between two skills."""

    source: SkillId
    target: SkillId
    relation: SkillRelationType
    version: Version
    strength: UnitInterval | None = None
    confidence: Confidence | None = None
    evidence: tuple[EvidenceId, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.source == self.target:
            raise ValueError("A skill cannot relate to itself")
