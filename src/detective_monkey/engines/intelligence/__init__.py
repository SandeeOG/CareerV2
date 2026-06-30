"""Intelligence Engine v1 — the single reasoning component.

Sits between the Assessment Engine and recommendation ranking:

    Assessment -> Intelligence Engine -> (Ranking) -> Recommendations -> Explanation

``IntelligenceEngine.build(...)`` is the only public method; it produces an
immutable :class:`StudentIntelligenceProfile`. ``rank_careers`` consumes that
profile to score careers — recommendation no longer performs interpretation.
"""

from .engine import (
    ENGINE_VERSION,
    IntelligenceEngine,
    SignalExtractor,
    TraitReasoner,
)
from .models import (
    CareerConstraints,
    ConversationContext,
    EvidenceItem,
    LearningStyle,
    ProfileMetadata,
    StudentIntelligenceProfile,
    StudentPreferences,
    StudentSignals,
    Trait,
    Vector,
    WorkEnvironment,
)
from .ranker import (
    DEFAULT_WEIGHTS,
    CareerRecommendation,
    RankingWeights,
    ScoringStrategy,
    rank_careers,
    score_career,
)
from . import mentor
from .mentor import (
    CareerInsight,
    Comparison,
    DailyAction,
    Opportunity,
    Readiness,
    Roadmap,
    RoadmapSkill,
    SkillGapAnalysis,
    StrengthView,
)

__all__ = [
    "IntelligenceEngine",
    "ENGINE_VERSION",
    "StudentIntelligenceProfile",
    "StudentSignals",
    "Trait",
    "EvidenceItem",
    "Vector",
    "LearningStyle",
    "WorkEnvironment",
    "CareerConstraints",
    "ConversationContext",
    "StudentPreferences",
    "ProfileMetadata",
    "rank_careers",
    "score_career",
    "CareerRecommendation",
    "RankingWeights",
    "DEFAULT_WEIGHTS",
    "ScoringStrategy",
    "SignalExtractor",
    "TraitReasoner",
    "mentor",
    "CareerInsight",
    "RoadmapSkill",
    "Readiness",
    "Opportunity",
    "DailyAction",
    "StrengthView",
    "SkillGapAnalysis",
    "Roadmap",
    "Comparison",
]
