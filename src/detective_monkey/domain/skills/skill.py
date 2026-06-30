"""Skill — a reusable, versioned capability node (13_SKILLS_MODEL.md §4, §8).

A skill is never plain text (13 §2): it is a globally unique, reusable graph
entity. ``StudentSkill`` and ``CareerSkill`` reference a ``Skill`` rather than
duplicating it (13 §13, §14, INV-06).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.attributes import Attributes
from ..common.identifiers import SkillId
from ..common.provenance import Provenance
from ..common.scores import ProficiencyLevel, UnitInterval
from ..common.versioning import Version
from ..knowledge_graph.ontology import VerificationStatus
from .taxonomy import SkillCategory, SkillLifecycle


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SkillClassification:
    """How a skill is organized (13 §8 Classification)."""

    category: SkillCategory
    subcategory: str = ""
    domain: str = ""
    complexity: UnitInterval | None = None
    transferability: UnitInterval | None = None


@dataclass(frozen=True, slots=True)
class SkillLearningProfile:
    """Learning characteristics of a skill (13 §8 Learning)."""

    difficulty: UnitInterval | None = None
    estimated_learning_hours: int | None = None
    prerequisite_level: ProficiencyLevel | None = None
    recommended_order: int | None = None

    def __post_init__(self) -> None:
        if self.estimated_learning_hours is not None and self.estimated_learning_hours < 0:
            raise ValueError("estimated_learning_hours must be >= 0")


@dataclass(frozen=True, slots=True)
class SkillMarketProfile:
    """Market characteristics of a skill (13 §8 Market).

    These are *normalized* indicators kept on the skill for convenience; the
    authoritative, time-aware market data lives in the Labour Market Model
    (15 §12 Skill Demand).
    """

    market_demand: UnitInterval | None = None
    growth_rate: UnitInterval | None = None
    future_importance: UnitInterval | None = None
    automation_resistance: UnitInterval | None = None
    industry_usage: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Skill:
    """A canonical, reusable skill (13 §8).

    Invariants: exactly one canonical identity (INV-01); no duplicates
    (INV-02); globally reusable (INV-06); historical versions remain available
    (INV-07).
    """

    id: SkillId
    canonical_name: str
    slug: str
    version: Version
    classification: SkillClassification
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    learning: SkillLearningProfile = field(default_factory=SkillLearningProfile)
    market: SkillMarketProfile = field(default_factory=SkillMarketProfile)
    lifecycle: SkillLifecycle = SkillLifecycle.CREATED
    verification_status: VerificationStatus = VerificationStatus.PROVISIONAL
    quality_score: UnitInterval | None = None
    coverage_score: UnitInterval | None = None
    provenance: Provenance | None = None
    metadata: Attributes = field(default_factory=Attributes)
    last_updated: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.canonical_name.strip():
            raise ValueError("Skill.canonical_name must be non-empty")
        if not self.slug.strip():
            raise ValueError("Skill.slug must be non-empty")
