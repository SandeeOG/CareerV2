"""Salary model (15_LABOUR_MARKET_MODEL.md §10).

Salary is multi-dimensional and PPP/tax aware. It lives here, never inside the
Career (15 §26 DO NOT "Store salary inside Career").
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.confidence import Confidence


@dataclass(frozen=True, slots=True)
class SalaryDistribution:
    """A salary distribution for one experience level / region (15 §10)."""

    currency: str
    confidence: Confidence
    minimum: float | None = None
    median: float | None = None
    average: float | None = None
    maximum: float | None = None
    ppp_adjusted: bool = False
    tax_region: str = ""
    level: str = ""  # e.g. entry / mid / senior

    def __post_init__(self) -> None:
        if not self.currency.strip():
            raise ValueError("SalaryDistribution.currency must be provided")
        lo, hi = self.minimum, self.maximum
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("minimum salary cannot exceed maximum salary")
