"""Career progression (12_CAREER_INTELLIGENCE_MODEL.md §19).

Represents advancement through levels. Alternative progression paths are
supported, so progression is modelled as one or more ordered paths rather than a
single linear chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProgressionStep:
    """One stage in a career progression path."""

    title: str
    order: int
    typical_years: int | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.order < 0:
            raise ValueError("ProgressionStep.order must be >= 0")


@dataclass(frozen=True, slots=True)
class ProgressionPath:
    """An ordered sequence of progression steps (one of possibly several)."""

    name: str
    steps: tuple[ProgressionStep, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        orders = [s.order for s in self.steps]
        if orders != sorted(orders):
            raise ValueError("ProgressionPath.steps must be ordered by 'order'")
