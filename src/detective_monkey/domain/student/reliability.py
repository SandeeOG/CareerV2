"""Reliability metrics (11_STUDENT_INTELLIGENCE_MODEL.md §9 Reliability Metrics).

Every profile includes confidence measurements describing how trustworthy the
profile is. These are distinct from per-score confidence: they describe the
profile as a whole.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.scores import UnitInterval


@dataclass(frozen=True, slots=True)
class ReliabilityMetrics:
    """Profile-level reliability measurements (all in [0, 1] where present)."""

    internal_consistency: UnitInterval | None = None
    response_reliability: UnitInterval | None = None
    evidence_completeness: UnitInterval | None = None
    missing_information: UnitInterval | None = None
    uncertainty: UnitInterval | None = None
