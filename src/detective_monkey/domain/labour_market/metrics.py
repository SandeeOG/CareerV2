"""Market metrics, geography and time (15_LABOUR_MARKET_MODEL.md §6, §7, §8, §9).

Every market metric references a timestamp (INV-03) and a geographic scope
(INV-04). Demand and supply are never merged (15 §9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.confidence import Confidence
from ..common.provenance import Provenance
from .enums import GeographicLevel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Geography:
    """A geographic scope for a market observation (15 §6)."""

    level: GeographicLevel
    name: str = ""

    def __post_init__(self) -> None:
        if self.level is not GeographicLevel.GLOBAL and not self.name.strip():
            raise ValueError("Non-global Geography requires a name")


@dataclass(frozen=True, slots=True)
class MarketMetric:
    """A single market measurement with full provenance (15 §8).

    Keeping value, confidence, source and timestamp together makes every metric
    independently traceable and forecast-aware.
    """

    name: str
    value: float
    confidence: Confidence
    provenance: Provenance
    observed_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("MarketMetric.name must be non-empty")


@dataclass(frozen=True, slots=True)
class DemandModel:
    """Employer need (15 §8). Distinct from supply."""

    metrics: tuple[MarketMetric, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SupplyModel:
    """Workforce availability (15 §9). Distinct from demand."""

    metrics: tuple[MarketMetric, ...] = field(default_factory=tuple)
