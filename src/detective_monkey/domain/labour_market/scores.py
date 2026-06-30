"""Labour Market Intelligence Scores (15_LABOUR_MARKET_MODEL.md §21, §22).

The Labour Market Model generates normalized indicators (all in [0, 1]) that the
Recommendation Engine consumes. Per 15 §2/§22, labour-market information adjusts
but never dominates student fit.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.scores import UnitInterval


@dataclass(frozen=True, slots=True)
class LabourMarketScores:
    """Normalized indicators exposed to the Recommendation Engine (15 §21).

    All fields are optional: an unknown indicator must not be fabricated as a
    neutral value (consistent with 11 INV-08).
    """

    demand_score: UnitInterval | None = None
    growth_score: UnitInterval | None = None
    salary_score: UnitInterval | None = None
    competition_score: UnitInterval | None = None
    mobility_score: UnitInterval | None = None
    ai_opportunity_score: UnitInterval | None = None
    automation_risk_score: UnitInterval | None = None
    career_stability_score: UnitInterval | None = None
