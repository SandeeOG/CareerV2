"""Confidence.

"Confidence without evidence is not trustworthy" (00 §8). Confidence is a
first-class, explainable quantity that propagates through the intelligence
pipeline and **never increases without additional evidence** (18 §14).

Confidence is distinct from a score (16 §11): a career may align strongly with a
student (high score) while the system is unsure (low confidence) because little
evidence exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .scores import UnitInterval


@dataclass(frozen=True, slots=True)
class ConfidenceFactor:
    """A single named contributor to (or detractor from) confidence.

    Keeping factors explicit makes confidence explainable (00 §7): the system can
    report *which factors reduced confidence*.
    """

    name: str
    impact: UnitInterval
    description: str = ""


@dataclass(frozen=True, slots=True)
class Confidence:
    """An explainable confidence value in [0, 1] with its contributing factors."""

    value: UnitInterval
    factors: tuple[ConfidenceFactor, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, value: float, *factors: ConfidenceFactor) -> "Confidence":
        return cls(UnitInterval(value), tuple(factors))

    @property
    def is_low(self) -> bool:
        return self.value.value < 0.5
