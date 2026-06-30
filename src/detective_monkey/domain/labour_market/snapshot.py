"""Labour Market Snapshot — the root entity (15_LABOUR_MARKET_MODEL.md §4, §5).

A snapshot captures the state of one career's market at a specific place and
time. Snapshots are immutable and never overwritten (INV-02); new observations
create new snapshots, preserving full history (15 §7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.identifiers import CareerId, LabourMarketSnapshotId
from ..common.provenance import Provenance
from ..common.versioning import Version
from .ai_impact import AIImpact, CareerStability, FutureOutlook
from .enums import RemoteWorkMode, TimeHorizon
from .metrics import DemandModel, Geography, SupplyModel
from .salary import SalaryDistribution
from .scores import LabourMarketScores


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class LabourMarketSnapshot:
    """An immutable, time- and region-aware view of a career's market."""

    id: LabourMarketSnapshotId
    career_id: CareerId
    geography: Geography
    period: str  # e.g. "Q1 2027" — the labelled observation period (15 §4)
    horizon: TimeHorizon
    version: Version
    demand: DemandModel = field(default_factory=DemandModel)
    supply: SupplyModel = field(default_factory=SupplyModel)
    salaries: tuple[SalaryDistribution, ...] = field(default_factory=tuple)
    ai_impact: AIImpact = field(default_factory=AIImpact)
    outlook: FutureOutlook | None = None
    stability: CareerStability = field(default_factory=CareerStability)
    remote_modes: tuple[RemoteWorkMode, ...] = field(default_factory=tuple)
    scores: LabourMarketScores = field(default_factory=LabourMarketScores)
    provenance: Provenance | None = None
    observed_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.period.strip():
            raise ValueError("LabourMarketSnapshot.period must be provided")
