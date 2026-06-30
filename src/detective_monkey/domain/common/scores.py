"""Score value objects.

The platform distinguishes several bounded numeric quantities. Encoding them as
value objects (rather than bare floats) enforces their ranges as invariants and
prevents accidentally mixing, say, a 0..100 alignment score with a 0..1
confidence (16 §10 Score Normalization, 13 §10 Skill Levels).

A central principle: **missing data never becomes fabricated data; unknown is
preferable to incorrect** (11 §13 INV-08). Therefore scores are never defaulted
to ``0``. Absence is represented by ``None`` at the field level, and an explicit
:class:`Unknown` sentinel is provided where a value is structurally required.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


@dataclass(frozen=True, slots=True, order=True)
class Score:
    """A normalized, comparable score in the closed interval [0, 100].

    Component scores entering the Recommendation Engine must be normalized to
    this range, monotonic and deterministic (16 §10).
    """

    value: float

    MIN: Final = 0.0
    MAX: Final = 100.0

    def __post_init__(self) -> None:
        if not (self.MIN <= self.value <= self.MAX):
            raise ValueError(f"Score must be within [0, 100], got {self.value}")


@dataclass(frozen=True, slots=True, order=True)
class UnitInterval:
    """A value in the closed interval [0, 1].

    Used for confidence, weights and probabilities (16 §9, 16 §11).
    """

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"UnitInterval must be within [0, 1], got {self.value}")


@dataclass(frozen=True, slots=True)
class ScoreRange:
    """An inclusive range of :class:`Score` values.

    Used, for example, for the optimal personality range of a career
    (12 §10): the Recommendation Engine checks whether a student's construct
    score falls within the career's optimal band.
    """

    low: Score
    high: Score

    def __post_init__(self) -> None:
        if self.low.value > self.high.value:
            raise ValueError("ScoreRange.low must be <= ScoreRange.high")

    def contains(self, score: Score) -> bool:
        return self.low.value <= score.value <= self.high.value


class ProficiencyLevel(int, Enum):
    """Evidence-based skill proficiency scale (13 §10).

    The platform stores *evidence*, not self-confidence. ``NO_EVIDENCE`` is the
    explicit representation of "we do not know" and is distinct from a measured
    level of zero capability.
    """

    NO_EVIDENCE = 0
    BASIC_AWARENESS = 1
    BEGINNER = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5


class Importance(str, Enum):
    """Qualitative importance / criticality used across career and memory layers.

    (12 §10/§11 importance, 16 weighting context, 19 §13 memory importance.)
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TEMPORARY = "temporary"


class Trend(str, Enum):
    """Directional trend for time-varying quantities (15 §12 skill demand)."""

    RISING = "rising"
    STABLE = "stable"
    FALLING = "falling"
    UNKNOWN = "unknown"
