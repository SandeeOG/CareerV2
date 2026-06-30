"""Career intelligence layers (12_CAREER_INTELLIGENCE_MODEL.md §7–§19).

Each layer of a career is modelled as a small, reusable value object. Layers
reference canonical entities (skills, subjects, ...) by id where one exists, and
otherwise describe a requirement directly. None of these layers contains
student-specific data (INV-04) or salary data (kept in the Labour Market Model).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.confidence import Confidence
from ..common.identifiers import SubjectId
from ..common.scores import Importance, ProficiencyLevel, ScoreRange, UnitInterval
from ..common.provenance import Provenance


@dataclass(frozen=True, slots=True)
class KnowledgeAreaRequirement:
    """What professionals must know (12 §7). Distinct from skills."""

    name: str
    importance: Importance
    description: str = ""


@dataclass(frozen=True, slots=True)
class SubjectRequirement:
    """An academic subject related to the career (12 §9)."""

    subject_id: SubjectId
    importance: Importance
    recommended_depth: str = ""
    prerequisites: tuple[SubjectId, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PersonalityRequirement:
    """Behavioural compatibility for a construct (12 §10).

    The Recommendation Engine compares the student's construct score against
    ``optimal_range``. ``construct`` names the construct in the Student
    Intelligence Model (11 §9 Construct Scores).
    """

    construct: str
    optimal_range: ScoreRange
    importance: Importance
    confidence: Confidence | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True, slots=True)
class WorkValue:
    """Motivational alignment (12 §11)."""

    name: str
    importance: Importance
    weight: UnitInterval | None = None
    description: str = ""


@dataclass(frozen=True, slots=True)
class WorkStyle:
    """A work-style characteristic (12 §12). Independent from personality."""

    name: str
    importance: Importance


@dataclass(frozen=True, slots=True)
class Responsibility:
    """A typical responsibility (12 §17)."""

    name: str
    frequency: UnitInterval | None = None
    importance: Importance | None = None
    difficulty: UnitInterval | None = None


@dataclass(frozen=True, slots=True)
class TechnologyRef:
    """A technology used in the career (12 §15). Distinct from a tool."""

    name: str
    importance: Importance | None = None


@dataclass(frozen=True, slots=True)
class ToolRef:
    """A tool used in the career (12 §16)."""

    name: str
    importance: Importance | None = None


@dataclass(frozen=True, slots=True)
class CertificationRef:
    """A professional certification relevant to the career (12 §14)."""

    name: str
    issuer: str = ""
    difficulty: UnitInterval | None = None
    industry_recognition: UnitInterval | None = None
    validity_years: int | None = None
    renewal_required: bool | None = None


@dataclass(frozen=True, slots=True)
class CompetencyRequirement:
    """An integrated competency expected of the career (14 §12 referenced here)."""

    name: str
    importance: Importance
    minimum_level: ProficiencyLevel | None = None
