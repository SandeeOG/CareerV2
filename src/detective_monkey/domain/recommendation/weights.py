"""Weight configuration (16_RECOMMENDATION_MODEL.md §8, §9).

"Weights are configurable. Weights are never hardcoded" (16 §8). Weight
configurations are versioned so historical recommendations remain reproducible
(16 §19). This object is configuration *data*; the engine that applies it is
Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.scores import UnitInterval
from ..common.versioning import Version
from .dimensions import Dimension


@dataclass(frozen=True, slots=True)
class WeightConfiguration:
    """A versioned mapping of dimension -> weight that sums to 1.0.

    Labour market is allowed only a small weight so it adjusts rather than
    dominates student fit (16 §25 DO NOT, 15 §2).
    """

    version: Version
    weights: tuple[tuple[Dimension, UnitInterval], ...] = field(default_factory=tuple)

    _TOLERANCE = 1e-6

    def __post_init__(self) -> None:
        dims = [d for d, _ in self.weights]
        if len(dims) != len(set(dims)):
            raise ValueError("WeightConfiguration has duplicate dimensions")
        total = sum(w.value for _, w in self.weights)
        if self.weights and abs(total - 1.0) > self._TOLERANCE:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

    def weight_for(self, dimension: Dimension) -> UnitInterval | None:
        for d, w in self.weights:
            if d == dimension:
                return w
        return None
