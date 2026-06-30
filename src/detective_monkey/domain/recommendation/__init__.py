"""Recommendation Model (16_RECOMMENDATION_MODEL.md).

The deterministic decision layer. Transforms canonical intelligence (student,
career, knowledge, labour market) into immutable, reproducible, evidence-bearing
recommendation objects. Explaining recommendations belongs to the AI layer, not
here.
"""

from .contracts import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationWarning,
    WarningSeverity,
)
from .dimensions import Dimension, DimensionScore
from .evidence import EvidenceCategory, RecommendationEvidence
from .recommendation import AlternativeCareer, Recommendation
from .weights import WeightConfiguration

__all__ = [
    "Dimension",
    "DimensionScore",
    "WeightConfiguration",
    "EvidenceCategory",
    "RecommendationEvidence",
    "Recommendation",
    "AlternativeCareer",
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendationWarning",
    "WarningSeverity",
]
