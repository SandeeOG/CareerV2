"""Stable identifiers for domain entities.

Every first-class domain object carries a typed identifier. Identifiers are
opaque strings; the domain never assumes a particular storage technology
generates them (00_ARCHITECTURE_PRINCIPLES.md §13). A ``uuid4``-based default
is provided purely so the domain is usable in isolation and in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class EntityId:
    """An opaque, immutable identifier for a domain entity.

    Subclasses give each root entity a distinct *type*, so a ``StudentId`` can
    never be silently used where a ``CareerId`` is expected.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("EntityId.value must be a non-empty string")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

    @classmethod
    def generate(cls) -> "EntityId":
        """Create a fresh identifier. Prefix encodes the concrete type."""
        return cls(f"{cls._prefix()}_{uuid4().hex}")

    @classmethod
    def _prefix(cls) -> str:
        # e.g. ``StudentId`` -> ``student``
        name = cls.__name__.removesuffix("Id")
        return name.lower() or "id"


class StudentId(EntityId):
    """Identifier for a Student (11_STUDENT_INTELLIGENCE_MODEL.md §4)."""


class ProfileId(EntityId):
    """Identifier for a Student Intelligence Profile (11 §9)."""


class CareerId(EntityId):
    """Identifier for a Career (12_CAREER_INTELLIGENCE_MODEL.md §4)."""


class SkillId(EntityId):
    """Identifier for a Skill (13_SKILLS_MODEL.md §4)."""


class EducationPathwayId(EntityId):
    """Identifier for an Education Pathway (14_EDUCATION_MODEL.md §4)."""


class QualificationId(EntityId):
    """Identifier for a Qualification (14 §8)."""


class InstitutionId(EntityId):
    """Identifier for an Institution (14 §9)."""


class CompetencyId(EntityId):
    """Identifier for a Competency (14 §12)."""


class SubjectId(EntityId):
    """Identifier for an academic Subject (12 §9, 14 §10)."""


class IndustryId(EntityId):
    """Identifier for an Industry (12 §5)."""


class RecommendationId(EntityId):
    """Identifier for a Recommendation (16_RECOMMENDATION_MODEL.md §17)."""


class ExplanationId(EntityId):
    """Identifier for an Explanation (10_DOMAIN_MODEL.md §12)."""


class EvidenceId(EntityId):
    """Identifier for an Evidence object (18 §6, 11 §8)."""


class NodeId(EntityId):
    """Identifier for a Knowledge Graph node (17_KNOWLEDGE_GRAPH.md §8)."""


class EdgeId(EntityId):
    """Identifier for a Knowledge Graph edge (17 §9)."""


class MemoryId(EntityId):
    """Identifier for a Memory record (19_MEMORY_ARCHITECTURE.md §12)."""


class LabourMarketSnapshotId(EntityId):
    """Identifier for a Labour Market Snapshot (15 §4)."""
