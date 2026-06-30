"""Stage 4 — Profile Construction.

Merges signals, inferred traits, constraints and confidence into one immutable
:class:`StudentIntelligenceProfile`.
"""

from __future__ import annotations

from .models import ProfileMetadata, StudentIntelligenceProfile
from .reasoner import ReasoningResult


def build_profile(
    reasoning: ReasoningResult,
    confidence: float,
    metadata: ProfileMetadata,
) -> StudentIntelligenceProfile:
    return StudentIntelligenceProfile(
        strengths=reasoning.strengths,
        weaknesses=reasoning.weaknesses,
        interests=reasoning.interests,
        personality=reasoning.personality,
        learning_style=reasoning.learning_style,
        preferred_work_environment=reasoning.work_environment,
        career_constraints=reasoning.career_constraints,
        skill_vector=reasoning.skill_vector,
        career_vector=reasoning.career_vector,
        evidence=reasoning.evidence,
        confidence=confidence,
        metadata=metadata,
    )
