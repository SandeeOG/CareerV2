"""Labour Market Model (15_LABOUR_MARKET_MODEL.md).

Represents how careers behave over time across industries, countries and time.
Immutable, versioned snapshots feed normalized scores to the Recommendation
Engine, where they adjust — but never dominate — student fit.
"""

from .ai_impact import AIImpact, CareerStability, FutureOutlook
from .enums import (
    GeographicLevel,
    MarketEventType,
    OutlookCategory,
    RemoteWorkMode,
    TimeHorizon,
)
from .metrics import DemandModel, Geography, MarketMetric, SupplyModel
from .salary import SalaryDistribution
from .scores import LabourMarketScores
from .snapshot import LabourMarketSnapshot

__all__ = [
    "LabourMarketSnapshot",
    "Geography",
    "MarketMetric",
    "DemandModel",
    "SupplyModel",
    "SalaryDistribution",
    "AIImpact",
    "FutureOutlook",
    "CareerStability",
    "LabourMarketScores",
    "GeographicLevel",
    "TimeHorizon",
    "OutlookCategory",
    "RemoteWorkMode",
    "MarketEventType",
]
