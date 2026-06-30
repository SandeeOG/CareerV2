"""AI impact and future outlook (15_LABOUR_MARKET_MODEL.md §13, §14, §18).

"The objective is not to eliminate careers. It is to understand how AI changes
them" (15 §13).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.confidence import Confidence
from ..common.scores import UnitInterval
from .enums import OutlookCategory


@dataclass(frozen=True, slots=True)
class AIImpact:
    """How AI affects a career (15 §13). All values normalized to [0, 1]."""

    automation_risk: UnitInterval | None = None
    ai_augmentation: UnitInterval | None = None
    ai_productivity_gain: UnitInterval | None = None
    human_dependency: UnitInterval | None = None
    creativity_requirement: UnitInterval | None = None
    social_requirement: UnitInterval | None = None


@dataclass(frozen=True, slots=True)
class FutureOutlook:
    """A forecast for a career (15 §14). Forecasts are never treated as facts."""

    category: OutlookCategory
    confidence: Confidence
    forecast_horizon_years: int | None = None

    def __post_init__(self) -> None:
        if self.forecast_horizon_years is not None and self.forecast_horizon_years < 0:
            raise ValueError("forecast_horizon_years must be >= 0")


@dataclass(frozen=True, slots=True)
class CareerStability:
    """Long-term resilience indicators (15 §18). All normalized to [0, 1]."""

    layoff_frequency: UnitInterval | None = None
    industry_volatility: UnitInterval | None = None
    demand_stability: UnitInterval | None = None
    economic_sensitivity: UnitInterval | None = None
    replacement_risk: UnitInterval | None = None
