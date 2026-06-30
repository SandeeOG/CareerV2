"""Recommendation Engine (25_RECOMMENDATION_ENGINE.md).

Re-exports the domain request/response contracts (defined in
``domain.recommendation``) alongside the orchestrator engine and pluggable
matchers.
"""

from ...domain.recommendation.contracts import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationWarning,
)
from .engine import RecommendationEngine
from .matchers import (
    CompetencyMatcher,
    EducationMatcher,
    GoalMatcher,
    KnowledgeMatcher,
    LabourMarketMatcher,
    MatchContext,
    MatchEngine,
    MatchResult,
    PsychologicalMatcher,
    SkillMatcher,
    default_matchers,
)

__all__ = [
    "RecommendationEngine",
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendationWarning",
    "MatchEngine",
    "MatchContext",
    "MatchResult",
    "PsychologicalMatcher",
    "SkillMatcher",
    "KnowledgeMatcher",
    "EducationMatcher",
    "CompetencyMatcher",
    "GoalMatcher",
    "LabourMarketMatcher",
    "default_matchers",
]
