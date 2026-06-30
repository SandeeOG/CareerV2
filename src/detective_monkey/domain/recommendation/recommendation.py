"""Recommendation — the immutable decision object (16_RECOMMENDATION_MODEL.md §17).

A recommendation is an evidence-based estimate of fit, not a prediction (16 §2).
It is deterministic and reproducible: identical inputs produce identical outputs
(INV-01, INV-08). It references — but never modifies — student intelligence and
career knowledge (INV-02, INV-03), and always includes evidence and confidence
(INV-04, INV-05).

The object pins every input version (INV-06) so historical recommendations stay
reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.confidence import Confidence
from ..common.identifiers import CareerId, RecommendationId
from ..common.scores import Score
from ..common.versioning import Version, VersionSet
from ..education.student_education import EducationGap
from ..skills.skill_gap import SkillGap
from .dimensions import DimensionScore
from .evidence import RecommendationEvidence


@dataclass(frozen=True, slots=True)
class AlternativeCareer:
    """A related career offered to widen exploration (16 §15, §16)."""

    career_id: CareerId
    relation: str  # similar / alternative / stretch / emerging
    score: Score | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Recommendation:
    """An immutable, reproducible career recommendation."""

    id: RecommendationId
    career_id: CareerId
    overall_score: Score
    confidence: Confidence
    recommendation_version: Version
    # Pins student profile / career / knowledge / labour-market / engine /
    # weight-config / explanation versions (16 §19).
    input_versions: VersionSet
    dimension_scores: tuple[DimensionScore, ...] = field(default_factory=tuple)
    evidence: tuple[RecommendationEvidence, ...] = field(default_factory=tuple)
    skill_gaps: tuple[SkillGap, ...] = field(default_factory=tuple)
    education_gaps: tuple[EducationGap, ...] = field(default_factory=tuple)
    alternative_careers: tuple[AlternativeCareer, ...] = field(default_factory=tuple)
    learning_plan_reference: str | None = None
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        # INV-04 / INV-05: recommendations always include evidence and confidence.
        if not self.evidence:
            raise ValueError(
                "Recommendation must include evidence "
                "(16_RECOMMENDATION_MODEL.md §20 INV-04)"
            )
