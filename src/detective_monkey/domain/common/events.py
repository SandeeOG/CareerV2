"""Domain events.

"Every major state transition emits a domain event" (10 §19). Events drive
analytics and future automation; they never carry behaviour (18 §11). Events are
immutable records of something that has already happened.

This module defines the base event and the canonical event names referenced by
the design documents. Engines (Phase 2) construct concrete events; the domain
only defines their shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from .attributes import Attributes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventName(str, Enum):
    """Canonical domain event names (10 §19, 18 §11, 31B_DOMAIN_EVENTS.md).

    The registry below is the authoritative catalogue (31B §25). System /
    infrastructure events (CacheInvalidated, EmailSent, ...) are deliberately
    excluded — they are not domain events (31B §5).
    """

    # Identity (31B §7)
    STUDENT_REGISTERED = "StudentRegistered"
    STUDENT_UPDATED = "StudentUpdated"
    STUDENT_ARCHIVED = "StudentArchived"

    # Assessment (31B §8)
    ASSESSMENT_STARTED = "AssessmentStarted"
    ASSESSMENT_COMPLETED = "AssessmentCompleted"
    ASSESSMENT_VALIDATED = "AssessmentValidated"
    ASSESSMENT_VERSION_PUBLISHED = "AssessmentVersionPublished"

    # Evidence (31B §9)
    EVIDENCE_COLLECTED = "EvidenceCollected"
    EVIDENCE_VALIDATED = "EvidenceValidated"
    EVIDENCE_VERIFIED = "EvidenceVerified"
    EVIDENCE_REJECTED = "EvidenceRejected"
    EVIDENCE_LINKED = "EvidenceLinked"
    EVIDENCE_ARCHIVED = "EvidenceArchived"

    # Feature (31B §10)
    FEATURE_COMPUTED = "FeatureComputed"
    FEATURE_UPDATED = "FeatureUpdated"
    FEATURE_DEPRECATED = "FeatureDeprecated"

    # Student intelligence (31B §11)
    STUDENT_PROFILE_GENERATED = "StudentProfileGenerated"
    STUDENT_PROFILE_PUBLISHED = "StudentProfilePublished"
    PROFILE_VERSION_CREATED = "ProfileVersionCreated"

    # Knowledge
    KNOWLEDGE_LINKED = "KnowledgeLinked"
    KNOWLEDGE_IMPORTED = "KnowledgeImported"
    SKILL_ADDED = "SkillAdded"
    CAREER_UPDATED = "CareerUpdated"

    # Recommendation (31B §12, 25 §20)
    CANDIDATE_GENERATED = "CandidateGenerated"
    MATCH_COMPLETED = "MatchCompleted"
    RANKING_COMPLETED = "RankingCompleted"
    RECOMMENDATION_GENERATED = "RecommendationGenerated"
    RECOMMENDATION_PUBLISHED = "RecommendationPublished"
    RECOMMENDATION_ACCEPTED = "RecommendationAccepted"
    RECOMMENDATION_REJECTED = "RecommendationRejected"
    RECOMMENDATION_ARCHIVED = "RecommendationArchived"

    # Explanation (31B §13)
    DECISION_GRAPH_BUILT = "DecisionGraphBuilt"
    EXPLANATION_GENERATED = "ExplanationGenerated"
    EXPLANATION_PUBLISHED = "ExplanationPublished"

    # Memory (31B §14)
    MEMORY_CREATED = "MemoryCreated"
    MEMORY_CONSOLIDATED = "MemoryConsolidated"
    MEMORY_ARCHIVED = "MemoryArchived"
    REFLECTION_RECORDED = "ReflectionRecorded"

    # Goals (31B §15)
    GOAL_CREATED = "GoalCreated"
    GOAL_UPDATED = "GoalUpdated"
    GOAL_COMPLETED = "GoalCompleted"
    GOAL_ARCHIVED = "GoalArchived"

    # Learning (31B §16)
    LEARNING_PLAN_CREATED = "LearningPlanCreated"
    COURSE_COMPLETED = "CourseCompleted"
    PROJECT_COMPLETED = "ProjectCompleted"
    SKILL_VERIFIED = "SkillVerified"
    MILESTONE_REACHED = "MilestoneReached"

    # Labour market (31B §17)
    MARKET_SNAPSHOT_IMPORTED = "MarketSnapshotImported"
    FORECAST_PUBLISHED = "ForecastPublished"

    # Reporting / feedback
    REPORT_CREATED = "ReportCreated"
    FEEDBACK_RECEIVED = "FeedbackReceived"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """An immutable record of a completed domain state transition (31B §6).

    Carries the metadata required for traceability and idempotent delivery
    (31B §6/§20, 405 §14, §18): a unique ``event_id``, the ``aggregate_type`` and
    ``aggregate_id`` it concerns, an event-schema ``version``, and
    ``correlation_id`` / ``causation_id`` linking events within a workflow.
    """

    name: EventName
    aggregate_id: str
    aggregate_type: str = ""
    event_id: str = field(default_factory=lambda: uuid4().hex)
    version: int = 1
    occurred_at: datetime = field(default_factory=_utcnow)
    correlation_id: str | None = None
    causation_id: str | None = None
    payload: Attributes = field(default_factory=Attributes)
