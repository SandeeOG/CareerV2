"""Premium DTOs for the User Experience Intelligence phase.

Transport-independent, serialization-friendly nested dataclasses surfaced through
the API to the SPA. No business logic — assembled by the application service from
the Intelligence Engine + mentor derivations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .dto import EvidenceDTO


@dataclass(frozen=True, slots=True)
class ReadinessDTO:
    score: int
    level: str
    explanation: str
    increases: tuple[str, ...]
    decreases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StrengthDTO:
    title: str
    confidence: int
    explanation: str


@dataclass(frozen=True, slots=True)
class OpportunityDTO:
    title: str
    detail: str
    employability_gain: int
    extra_careers: int


@dataclass(frozen=True, slots=True)
class ActionDTO:
    title: str
    detail: str
    impact: str


@dataclass(frozen=True, slots=True)
class LearningStyleDTO:
    style: str
    explanation: str


@dataclass(frozen=True, slots=True)
class DashboardDTO:
    student_id: str
    greeting: str
    ai_summary: str
    readiness: ReadinessDTO
    strengths: tuple[StrengthDTO, ...]
    learning_style: LearningStyleDTO
    opportunity: OpportunityDTO
    todays_action: ActionDTO
    suggested_questions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PremiumCardDTO:
    career_id: str
    name: str
    score: float
    confidence: float
    summary: str
    match_explanation: tuple[str, ...]
    strengths_used: tuple[str, ...]
    challenges: tuple[str, ...]
    required_education: tuple[str, ...]
    salary_range: str
    future_demand: str
    automation_risk: str
    remote_compatibility: str
    skill_gaps: tuple[str, ...]
    estimated_learning_weeks: int
    next_actions: tuple[str, ...]
    alternatives: tuple[str, ...]
    evidence: tuple[EvidenceDTO, ...]


@dataclass(frozen=True, slots=True)
class RecommendationsDTO:
    student_id: str
    cards: tuple[PremiumCardDTO, ...]


@dataclass(frozen=True, slots=True)
class MissingSkillDTO:
    name: str
    importance: str
    weeks: int
    employability_gain: int


@dataclass(frozen=True, slots=True)
class SkillGapDTO:
    career_id: str
    name: str
    current_compatibility: int
    projected_compatibility: int
    strengths: tuple[str, ...]
    missing: tuple[MissingSkillDTO, ...]


@dataclass(frozen=True, slots=True)
class RoadmapStepDTO:
    title: str
    duration: str
    difficulty: str
    importance: str
    resources: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class RoadmapDTO:
    career_id: str
    goal: str
    steps: tuple[RoadmapStepDTO, ...]


@dataclass(frozen=True, slots=True)
class ComparisonRowDTO:
    dimension: str
    a: str
    b: str
    winner: str


@dataclass(frozen=True, slots=True)
class ComparisonDTO:
    career_a: str
    career_b: str
    rows: tuple[ComparisonRowDTO, ...]
    recommendation: str


@dataclass(frozen=True, slots=True)
class CoachReplyDTO:
    response: str
    suggestions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CareerDetailDTO:
    career_id: str
    name: str
    compatibility: float
    overview: str
    personal_note: str
    daily_work: tuple[str, ...]
    responsibilities: tuple[str, ...]
    progression: tuple[tuple[str, str], ...]
    salary_range: str
    required_education: tuple[str, ...]
    certifications: tuple[str, ...]
    demand: str
    future_outlook: str
    automation_risk: str
    remote_compatibility: str
    related_careers: tuple[str, ...]
    roadmap: RoadmapDTO
