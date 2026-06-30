"""Recommendation ranking driven by the Intelligence Profile.

This is the only place career fit is scored. The Recommendation flow no longer
reasons — it receives a :class:`StudentIntelligenceProfile` and ranks careers
through weighted scoring, returning rich, explainable
:class:`CareerRecommendation` objects (top strengths, interests, matching
skills, evidence used, confidence and missing information).

All weights live in :class:`RankingWeights` — no magic numbers, easy to tune.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ...domain.career.career import Career
from ...domain.common.scores import Score
from .models import EvidenceItem, StudentIntelligenceProfile

# Career construct (assessment vocabulary) -> profile skill_vector key.
_CONSTRUCT_TO_SKILL = {
    "analytical_thinking": "problem_solving",
    "creativity": "creativity",
    "leadership": "leadership",
    "communication": "communication",
    "conscientiousness": "discipline",
    "curiosity": "learning_agility",
}

# Career-name keyword -> interest area (matches reasoner._INTEREST_AREAS keys).
_AREA_KEYWORDS = {
    "Programming & Technology": ("software", "engineer", "developer", "programming", "data"),
    "Research & Science": ("research", "scientist", "science"),
    "Design & Creative": ("design", "ux", "ui", "creative", "artist"),
    "Business & Leadership": ("manager", "product", "business", "lead"),
    "Communication & Social": ("communication", "teacher", "counsel", "social"),
}

_NEUTRAL = 0.6


@dataclass(frozen=True, slots=True)
class RankingWeights:
    """Tunable weights for career scoring (sum of core dims is normalized;
    labour market is an additive bonus so it adjusts but never dominates)."""

    skill_match: float = 0.25
    interest_match: float = 0.25
    personality_match: float = 0.30
    learning_style_match: float = 0.10
    career_constraints: float = 0.10
    labour_market_bonus: float = 0.10


DEFAULT_WEIGHTS = RankingWeights()


@dataclass(frozen=True, slots=True)
class CareerRecommendation:
    """A ranked, explainable career match produced from the profile."""

    career_id: str
    name: str
    score: float            # 0-100
    confidence: float       # 0-1
    reasons: tuple[str, ...]
    top_strengths: tuple[str, ...]
    top_interests: tuple[str, ...]
    matching_skills: tuple[str, ...]
    evidence: tuple[EvidenceItem, ...]
    missing_information: tuple[str, ...]
    dimension_scores: tuple[tuple[str, float], ...] = field(default_factory=tuple)


@runtime_checkable
class ScoringStrategy(Protocol):
    """Extension point for future Bayesian / embedding / learning-to-rank scorers."""

    def __call__(
        self, profile: StudentIntelligenceProfile, career: Career
    ) -> CareerRecommendation: ...


# -- dimension scorers (each returns 0-1) ----------------------------------


def _personality_match(profile: StudentIntelligenceProfile, career: Career) -> float:
    reqs = career.personality
    if not reqs:
        return _NEUTRAL
    total_w = 0.0
    acc = 0.0
    for req in reqs:
        skill_key = _CONSTRUCT_TO_SKILL.get(req.construct)
        value01 = profile.skill_vector.get(skill_key, 0.5) if skill_key else 0.5
        value = Score(max(0.0, min(100.0, value01 * 100.0)))
        if req.optimal_range.contains(value):
            fit = 1.0
        else:
            low, high = req.optimal_range.low.value, req.optimal_range.high.value
            distance = (low - value.value) if value.value < low else (value.value - high)
            fit = max(0.0, 1.0 - distance / 100.0)
        w = _importance_weight(req.importance)
        acc += fit * w
        total_w += w
    return acc / total_w if total_w else _NEUTRAL


def _interest_area(career: Career) -> str | None:
    name = career.identity.canonical_name.lower()
    for area, keywords in _AREA_KEYWORDS.items():
        if any(k in name for k in keywords):
            return area
    return None


def _interest_match(profile: StudentIntelligenceProfile, career: Career) -> tuple[float, str | None]:
    area = _interest_area(career)
    if area is not None:
        return profile.career_vector.get(area, _NEUTRAL), area
    # No mapping: use the student's strongest interest affinity as a soft signal.
    top = profile.career_vector.top(1)
    return (top[0][1] if top else _NEUTRAL), (top[0][0] if top else None)


def _skill_match(profile: StudentIntelligenceProfile, career: Career
                 ) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    if not career.skills:
        return _NEUTRAL, (), ()
    technical = profile.skill_vector.get("technical", 0.5)
    matching: list[str] = []
    missing: list[str] = []
    for cs in career.skills:
        (matching if technical >= 0.5 else missing).append(cs.skill_id.value)
    return technical, tuple(matching), tuple(missing)


def _importance_weight(importance) -> float:
    from ...domain.common.scores import Importance
    return {
        Importance.CRITICAL: 1.0, Importance.HIGH: 0.8, Importance.MEDIUM: 0.5,
        Importance.LOW: 0.3, Importance.TEMPORARY: 0.1,
    }.get(importance, 0.5)


# -- public ranking --------------------------------------------------------


def score_career(
    profile: StudentIntelligenceProfile,
    career: Career,
    weights: RankingWeights = DEFAULT_WEIGHTS,
    labour_bonus: float = 0.0,
) -> CareerRecommendation:
    personality = _personality_match(profile, career)
    interest, area = _interest_match(profile, career)
    skill, matching_skills, missing_skills = _skill_match(profile, career)
    learning = _NEUTRAL          # extension point: map career -> preferred style
    constraints = 1.0            # extension point: country/remote/study checks

    core_w = (weights.skill_match + weights.interest_match + weights.personality_match
              + weights.learning_style_match + weights.career_constraints)
    core = (
        weights.skill_match * skill
        + weights.interest_match * interest
        + weights.personality_match * personality
        + weights.learning_style_match * learning
        + weights.career_constraints * constraints
    ) / (core_w or 1.0)
    final = max(0.0, min(1.0, core + weights.labour_market_bonus * labour_bonus))

    # Explanation
    reasons: list[str] = []
    if personality >= 0.7:
        reasons.append("Strong fit with the role's personality profile")
    for t in profile.top_strengths(2):
        reasons.append(f"Excellent {t.name.lower()}")
    if area and interest >= 0.6:
        reasons.append(f"Strong {area} interest")
    if skill >= 0.6 and matching_skills:
        reasons.append("High technical aptitude for the required skills")
    if not reasons:
        reasons.append("Moderate overall alignment with your profile")

    evidence: list[EvidenceItem] = []
    for t in (*profile.top_strengths(2), *profile.top_interests(1)):
        evidence.extend(t.evidence)

    missing: list[str] = []
    if missing_skills:
        missing.append("Skills to develop: " + ", ".join(missing_skills))
    if profile.confidence < 0.5:
        missing.append("Limited assessment data — confidence is low")
    if labour_bonus == 0.0:
        missing.append("No labour-market data available for this career")

    rec_confidence = profile.confidence * (0.6 + 0.4 * (1.0 if career.personality else 0.5))

    return CareerRecommendation(
        career_id=career.id.value,
        name=career.identity.canonical_name,
        score=round(final * 100.0, 1),
        confidence=round(min(1.0, rec_confidence), 3),
        reasons=tuple(reasons),
        top_strengths=tuple(t.name for t in profile.top_strengths(3)),
        top_interests=tuple(t.name for t in profile.top_interests(3)),
        matching_skills=matching_skills,
        evidence=tuple(evidence),
        missing_information=tuple(missing),
        dimension_scores=(
            ("personality", round(personality, 3)),
            ("interest", round(interest, 3)),
            ("skill", round(skill, 3)),
            ("learning_style", round(learning, 3)),
            ("constraints", round(constraints, 3)),
        ),
    )


def rank_careers(
    profile: StudentIntelligenceProfile,
    careers: tuple[Career, ...],
    weights: RankingWeights = DEFAULT_WEIGHTS,
    labour_bonus: dict[str, float] | None = None,
) -> tuple[CareerRecommendation, ...]:
    """Score and rank careers against the profile (deterministic)."""
    bonus = labour_bonus or {}
    scored = [
        score_career(profile, c, weights, bonus.get(c.id.value, 0.0)) for c in careers
    ]
    scored.sort(key=lambda r: (-r.score, -r.confidence, r.career_id))
    return tuple(scored)
