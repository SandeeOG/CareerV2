"""Career similarity graph (12_CAREER_INTELLIGENCE_MODEL.md §20, §25).

Careers relate to other careers through typed, metadata-bearing relationships.
Similarity is graph-based and may be asymmetric (12 §25). These relationships
enable recommendation expansion and alternative-career generation (16 §15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..common.confidence import Confidence
from ..common.identifiers import CareerId, EvidenceId
from ..common.scores import UnitInterval
from ..common.versioning import Version


class CareerRelationType(str, Enum):
    """Relationship types between careers (12 §20)."""

    SIMILAR = "similar"
    ALTERNATIVE = "alternative"
    PREREQUISITE = "prerequisite"
    SUCCESSOR = "successor"
    SPECIALIZATION = "specialization"
    GENERALIZATION = "generalization"
    CROSSOVER = "crossover"
    EMERGING = "emerging"
    ADJACENT = "adjacent"


@dataclass(frozen=True, slots=True)
class CareerRelation:
    """A directed, typed relationship from one career to another."""

    source: CareerId
    target: CareerId
    relation: CareerRelationType
    version: Version
    similarity: UnitInterval | None = None
    confidence: Confidence | None = None
    evidence: tuple[EvidenceId, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.source == self.target:
            raise ValueError("A career cannot relate to itself")
