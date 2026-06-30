"""Recommendation matching dimensions (16_RECOMMENDATION_MODEL.md §7, §8).

Recommendations are multi-dimensional; each dimension produces an independent,
normalized score (16 §7, §10). The dimensions are fixed domain concepts; the
*weights* applied to them are configurable (see ``weights.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..common.confidence import Confidence
from ..common.identifiers import EvidenceId
from ..common.scores import Score


class Dimension(str, Enum):
    """The independent matching dimensions (16 §7)."""

    PSYCHOLOGICAL = "psychological"
    SKILL = "skill"
    KNOWLEDGE = "knowledge"
    EDUCATION = "education"
    INTEREST = "interest"
    COMPETENCY = "competency"
    GOAL = "goal"
    LABOUR_MARKET = "labour_market"


@dataclass(frozen=True, slots=True)
class DimensionScore:
    """An independent, normalized score for one matching dimension.

    Per 25_RECOMMENDATION_ENGINE.md §6/§7 each match engine produces a *score,
    confidence and evidence* together, and INV-02 requires that "every score
    references evidence". Confidence is carried per dimension so the
    Recommendation Engine can aggregate it upward (§17 Confidence Aggregation)
    without exceeding the supporting evidence.

    Both ``confidence`` and ``evidence`` are optional so a partially-specified or
    test fixture remains constructible, but a production match engine is expected
    to populate them.
    """

    dimension: Dimension
    score: Score
    confidence: Confidence | None = None
    evidence: tuple[EvidenceId, ...] = field(default_factory=tuple)
