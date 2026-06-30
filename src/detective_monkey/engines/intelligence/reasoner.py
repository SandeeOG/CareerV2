"""Stage 2 + 3 — Trait Inference and Evidence Collection.

Pure deterministic reasoning (no LLM). Turns the signal vector into strengths,
weaknesses, interests, personality, learning style, work environment, skill and
career vectors — every inferred trait carrying evidence for later display.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    CareerConstraints,
    ConversationContext,
    EvidenceItem,
    LearningStyle,
    StudentPreferences,
    StudentSignals,
    Trait,
    Vector,
    WorkEnvironment,
)

# Named thresholds (no magic numbers).
STRONG_THRESHOLD = 0.66
WEAK_THRESHOLD = 0.40
INTEREST_THRESHOLD = 0.55

_SIGNAL_LABELS = {
    "logical": "Logical reasoning",
    "creative": "Creative thinking",
    "leadership": "Leadership",
    "verbal": "Verbal communication",
    "social": "Social & interpersonal skill",
    "technical": "Technical aptitude",
    "academic": "Academic discipline",
    "learning_speed": "Learning agility",
    "motivation": "Motivation",
    "risk_tolerance": "Risk tolerance",
    "confidence": "Self-confidence",
}

# Interest area -> (signal, weight) contributions.
_INTEREST_AREAS = {
    "Programming & Technology": (("technical", 0.6), ("logical", 0.4)),
    "Research & Science": (("logical", 0.5), ("learning_speed", 0.5)),
    "Design & Creative": (("creative", 0.8), ("learning_speed", 0.2)),
    "Business & Leadership": (("leadership", 0.6), ("social", 0.4)),
    "Communication & Social": (("verbal", 0.6), ("social", 0.4)),
}


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    strengths: tuple[Trait, ...]
    weaknesses: tuple[Trait, ...]
    interests: tuple[Trait, ...]
    personality: tuple[Trait, ...]
    learning_style: LearningStyle
    work_environment: WorkEnvironment
    career_constraints: CareerConstraints
    skill_vector: Vector
    career_vector: Vector
    evidence: tuple[EvidenceItem, ...]


def _evidence_for(signal: str, value: float) -> EvidenceItem:
    label = _SIGNAL_LABELS.get(signal, signal)
    return EvidenceItem(
        claim=label,
        source=f"Assessment signal: {label}",
        detail=f"Normalized score {value:.2f}",
        weight=value,
        confidence=min(1.0, 0.5 + value / 2),
    )


def _strengths_weaknesses(signals: StudentSignals) -> tuple[tuple[Trait, ...], tuple[Trait, ...]]:
    strengths: list[Trait] = []
    weaknesses: list[Trait] = []
    for name, value in signals.as_pairs():
        label = _SIGNAL_LABELS.get(name, name)
        if value >= STRONG_THRESHOLD:
            strengths.append(Trait(label, value, (_evidence_for(name, value),)))
        elif value <= WEAK_THRESHOLD:
            weaknesses.append(Trait(label, value, (_evidence_for(name, value),)))
    strengths.sort(key=lambda t: -t.score)
    weaknesses.sort(key=lambda t: t.score)
    return tuple(strengths), tuple(weaknesses)


def _interests(signals: StudentSignals) -> tuple[tuple[Trait, ...], Vector]:
    components: list[tuple[str, float]] = []
    interests: list[Trait] = []
    for area, contributions in _INTEREST_AREAS.items():
        score = sum(signals.get(sig) * w for sig, w in contributions)
        components.append((area, score))
        if score >= INTEREST_THRESHOLD:
            evidence = tuple(
                _evidence_for(sig, signals.get(sig)) for sig, _ in contributions
            )
            interests.append(Trait(area, score, evidence))
    interests.sort(key=lambda t: -t.score)
    return tuple(interests), Vector(tuple(components))


def _personality(signals: StudentSignals) -> tuple[Trait, ...]:
    spec = (
        ("Openness", (signals.creative + signals.learning_speed) / 2,
         ("creative", "learning_speed")),
        ("Conscientiousness", signals.academic, ("academic",)),
        ("Extraversion", signals.social, ("social",)),
        ("Leadership orientation", signals.leadership, ("leadership",)),
        ("Resilience", signals.confidence, ("confidence",)),
    )
    return tuple(
        Trait(name, score, tuple(_evidence_for(s, signals.get(s)) for s in sigs))
        for name, score, sigs in spec
    )


def _learning_style(signals: StudentSignals) -> LearningStyle:
    scores = {
        LearningStyle.ANALYTICAL: signals.logical,
        LearningStyle.EXPLORATORY: (signals.learning_speed + signals.creative) / 2,
        LearningStyle.COLLABORATIVE: signals.social,
        LearningStyle.PRACTICAL: signals.technical,
        LearningStyle.REFLECTIVE: signals.academic,
    }
    return max(scores, key=lambda k: scores[k])


def _work_environment(signals: StudentSignals) -> WorkEnvironment:
    scores = {
        WorkEnvironment.TEAM: signals.social,
        WorkEnvironment.INDEPENDENT: 1.0 - signals.social,
        WorkEnvironment.RESEARCH: (signals.logical + signals.learning_speed) / 2,
        WorkEnvironment.DYNAMIC: signals.risk_tolerance,
        WorkEnvironment.STRUCTURED: (signals.academic + (1.0 - signals.risk_tolerance)) / 2,
    }
    return max(scores, key=lambda k: scores[k])


def _skill_vector(signals: StudentSignals) -> Vector:
    return Vector((
        ("problem_solving", signals.logical),
        ("communication", signals.verbal),
        ("creativity", signals.creative),
        ("leadership", signals.leadership),
        ("technical", signals.technical),
        ("collaboration", signals.social),
        ("discipline", signals.academic),
        ("learning_agility", signals.learning_speed),
    ))


def _constraints(preferences: StudentPreferences | None) -> CareerConstraints:
    if preferences is None:
        return CareerConstraints()
    return CareerConstraints(
        max_study_years=preferences.max_study_years,
        preferred_countries=preferences.preferred_countries,
        remote_only=preferences.remote_only,
    )


def infer(
    signals: StudentSignals,
    conversation: ConversationContext | None = None,
    preferences: StudentPreferences | None = None,
) -> ReasoningResult:
    """Run deterministic trait inference + evidence collection (Stages 2-3)."""
    strengths, weaknesses = _strengths_weaknesses(signals)
    interests, career_vector = _interests(signals)
    personality = _personality(signals)

    evidence: list[EvidenceItem] = []
    for trait in (*strengths, *interests):
        evidence.extend(trait.evidence)
    if conversation is not None and conversation.messages:
        evidence.append(EvidenceItem(
            claim="Stated interests",
            source="Conversation",
            detail=conversation.text()[:120],
            weight=0.5,
            confidence=0.6,
        ))

    return ReasoningResult(
        strengths=strengths,
        weaknesses=weaknesses,
        interests=interests,
        personality=personality,
        learning_style=_learning_style(signals),
        work_environment=_work_environment(signals),
        career_constraints=_constraints(preferences),
        skill_vector=_skill_vector(signals),
        career_vector=career_vector,
        evidence=tuple(evidence),
    )
