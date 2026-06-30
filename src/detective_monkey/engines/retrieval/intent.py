"""Intent classification (27_KNOWLEDGE_RETRIEVAL_ARCHITECTURE.md §5).

Every query is classified before retrieval (§4). Intent determines the retrieval
strategy. The default classifier is deterministic and rule-based; it can be
replaced without changing the engine contract.
"""

from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    """Query intents (27 §5)."""

    CAREER_EXPLORATION = "career_exploration"
    RECOMMENDATION = "recommendation"
    EXPLANATION = "explanation"
    SKILL_GAP = "skill_gap"
    LEARNING_PLAN = "learning_plan"
    UNIVERSITY = "university"
    SCHOLARSHIP = "scholarship"
    CONVERSATION = "conversation"
    PLANNING = "planning"


# Ordered keyword rules; first match wins (deterministic).
_RULES: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (Intent.EXPLANATION, ("why", "explain", "reason", "because")),
    (Intent.SKILL_GAP, ("skill gap", "missing skill", "what skills", "skills do i")),
    (Intent.LEARNING_PLAN, ("learn", "course", "study plan", "learning plan", "improve")),
    (Intent.UNIVERSITY, ("university", "college", "degree", "admission")),
    (Intent.SCHOLARSHIP, ("scholarship", "funding", "grant")),
    (Intent.RECOMMENDATION, ("recommend", "best career", "suit me", "fit me")),
    (Intent.PLANNING, ("plan", "roadmap", "next step", "timeline")),
    (Intent.CAREER_EXPLORATION, ("explore", "career options", "what careers", "tell me about")),
)


def classify(query: str) -> Intent:
    q = query.lower()
    for intent, keywords in _RULES:
        if any(k in q for k in keywords):
            return intent
    return Intent.CONVERSATION
