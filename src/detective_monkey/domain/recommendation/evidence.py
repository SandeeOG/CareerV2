"""Recommendation evidence (16_RECOMMENDATION_MODEL.md §12, §22).

Every recommendation requires evidence, stored independently and organized by
category. Evidence is generated *before* explanations (16 §25 DO); the
Explanation Engine consumes it but never computes it (16 §22).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..common.identifiers import EvidenceId
from .dimensions import Dimension


class EvidenceCategory(str, Enum):
    """Categories of recommendation evidence (16 §12)."""

    STRENGTH_ALIGNMENT = "strength_alignment"
    SKILL_ALIGNMENT = "skill_alignment"
    INTEREST_ALIGNMENT = "interest_alignment"
    EDUCATION_ALIGNMENT = "education_alignment"
    BEHAVIOURAL_ALIGNMENT = "behavioural_alignment"
    GOAL_ALIGNMENT = "goal_alignment"
    LABOUR_MARKET_ALIGNMENT = "labour_market_alignment"


@dataclass(frozen=True, slots=True)
class RecommendationEvidence:
    """A piece of evidence supporting (one dimension of) a recommendation."""

    category: EvidenceCategory
    summary: str
    dimension: Dimension | None = None
    sources: tuple[EvidenceId, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("RecommendationEvidence.summary must be non-empty")
