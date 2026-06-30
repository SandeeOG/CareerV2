"""Intelligence domain models.

Immutable, strongly-typed value objects for the Intelligence Layer. No dicts, no
``Any``. These are the vocabulary of the single reasoning component: signals,
traits, evidence and the :class:`StudentIntelligenceProfile` that becomes the
sole input to recommendation ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


def _unit(value: float, name: str) -> float:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be within [0, 1], got {value}")
    return value


# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------


class LearningStyle(str, Enum):
    ANALYTICAL = "analytical"
    EXPLORATORY = "exploratory"
    PRACTICAL = "practical"
    COLLABORATIVE = "collaborative"
    REFLECTIVE = "reflective"


class WorkEnvironment(str, Enum):
    TEAM = "team"
    INDEPENDENT = "independent"
    STRUCTURED = "structured"
    DYNAMIC = "dynamic"
    RESEARCH = "research"


# --------------------------------------------------------------------------
# Evidence + traits
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """A single piece of evidence supporting an inferred trait or score.

    Surfaced in the UI so every recommendation is explainable.
    """

    claim: str          # what this evidence supports, e.g. "Investigative interest"
    source: str         # where it came from, e.g. "Assessment: logical reasoning"
    detail: str = ""    # human-readable detail
    weight: float = 1.0
    confidence: float = 1.0

    def __post_init__(self) -> None:
        _unit(self.confidence, "EvidenceItem.confidence")
        if self.weight < 0:
            raise ValueError("EvidenceItem.weight must be >= 0")


@dataclass(frozen=True, slots=True)
class Trait:
    """An inferred characteristic with a [0,1] score and its evidence."""

    name: str
    score: float
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _unit(self.score, "Trait.score")
        if not self.name.strip():
            raise ValueError("Trait.name must be non-empty")


@dataclass(frozen=True, slots=True)
class Vector:
    """An immutable named vector (e.g. skill or career affinities)."""

    components: tuple[tuple[str, float], ...] = field(default_factory=tuple)

    def get(self, name: str, default: float = 0.0) -> float:
        for k, v in self.components:
            if k == name:
                return v
        return default

    def top(self, n: int) -> tuple[tuple[str, float], ...]:
        return tuple(sorted(self.components, key=lambda c: -c[1])[:n])


# --------------------------------------------------------------------------
# Signals (Stage 1 output)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StudentSignals:
    """Normalized [0,1] signals extracted from assessment/conversation/history."""

    academic: float
    logical: float
    verbal: float
    creative: float
    social: float
    leadership: float
    technical: float
    learning_speed: float
    risk_tolerance: float
    motivation: float
    confidence: float

    def __post_init__(self) -> None:
        for name, value in self.as_pairs():
            _unit(value, f"StudentSignals.{name}")

    def as_pairs(self) -> tuple[tuple[str, float], ...]:
        return (
            ("academic", self.academic),
            ("logical", self.logical),
            ("verbal", self.verbal),
            ("creative", self.creative),
            ("social", self.social),
            ("leadership", self.leadership),
            ("technical", self.technical),
            ("learning_speed", self.learning_speed),
            ("risk_tolerance", self.risk_tolerance),
            ("motivation", self.motivation),
            ("confidence", self.confidence),
        )

    def get(self, name: str, default: float = 0.0) -> float:
        for k, v in self.as_pairs():
            if k == name:
                return v
        return default


# --------------------------------------------------------------------------
# Inputs (optional)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """Optional conversational signal source (mentions, stated interests)."""

    messages: tuple[str, ...] = field(default_factory=tuple)

    def text(self) -> str:
        return " ".join(self.messages).lower()


@dataclass(frozen=True, slots=True)
class StudentPreferences:
    """Optional explicit preferences/constraints declared by the student."""

    dream_careers: tuple[str, ...] = field(default_factory=tuple)
    preferred_countries: tuple[str, ...] = field(default_factory=tuple)
    work_preferences: tuple[str, ...] = field(default_factory=tuple)
    max_study_years: int | None = None
    remote_only: bool = False


@dataclass(frozen=True, slots=True)
class CareerConstraints:
    """Hard/soft constraints the recommendation ranker must respect."""

    max_study_years: int | None = None
    preferred_countries: tuple[str, ...] = field(default_factory=tuple)
    remote_only: bool = False


@dataclass(frozen=True, slots=True)
class ProfileMetadata:
    engine_version: str
    signal_count: int
    evidence_count: int
    assessment_completeness: float


# --------------------------------------------------------------------------
# The Student Intelligence Profile (Stage 4 output)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StudentIntelligenceProfile:
    """The single, interpretation-rich input to recommendation ranking.

    Distinct from the low-level ``domain.student.profile.StudentIntelligenceProfile``
    (raw construct/domain scores): this object carries *interpreted* strengths,
    interests, personality, learning style, vectors and evidence with an overall
    confidence. It is immutable.
    """

    strengths: tuple[Trait, ...]
    weaknesses: tuple[Trait, ...]
    interests: tuple[Trait, ...]
    personality: tuple[Trait, ...]
    learning_style: LearningStyle
    preferred_work_environment: WorkEnvironment
    career_constraints: CareerConstraints
    skill_vector: Vector
    career_vector: Vector
    evidence: tuple[EvidenceItem, ...]
    confidence: float
    metadata: ProfileMetadata

    def __post_init__(self) -> None:
        _unit(self.confidence, "StudentIntelligenceProfile.confidence")

    def top_strengths(self, n: int = 3) -> tuple[Trait, ...]:
        return tuple(sorted(self.strengths, key=lambda t: -t.score)[:n])

    def top_interests(self, n: int = 3) -> tuple[Trait, ...]:
        return tuple(sorted(self.interests, key=lambda t: -t.score)[:n])
