"""Evaluation metrics (29_INTELLIGENCE_EVALUATION.md §3, §25, §26).

Every metric is versioned (INV-02) and auditable (INV-05). Business and technical
metrics are kept separate (INV-06) via the ``business`` flag. Evaluation never
modifies production outputs (INV-01); these are read-only measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.versioning import Version

METRICS_VERSION = Version(1, "P2")


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    value: float
    business: bool = False
    detail: str = ""
    version: Version = METRICS_VERSION


@dataclass(frozen=True, slots=True)
class MetricGroup:
    """Metrics for one evaluation layer (29 §3)."""

    layer: str
    metrics: tuple[Metric, ...] = field(default_factory=tuple)

    def get(self, name: str) -> Metric | None:
        for m in self.metrics:
            if m.name == name:
                return m
        return None


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """A versioned, auditable evaluation report (29 §25)."""

    groups: tuple[MetricGroup, ...] = field(default_factory=tuple)
    version: Version = METRICS_VERSION

    def group(self, layer: str) -> MetricGroup | None:
        for g in self.groups:
            if g.layer == layer:
                return g
        return None
