"""Tests for the Recommendation Engine contract surface (25_RECOMMENDATION_ENGINE.md).

These cover the additive changes doc 25 made necessary: per-dimension
confidence/evidence, and the RecommendationRequest/Response data contracts.
"""

from __future__ import annotations

import pytest

from detective_monkey.domain.career import Career, CareerIdentity
from detective_monkey.domain.common import (
    Confidence,
    EvidenceId,
    Score,
    UnitInterval,
    Version,
    VersionSet,
)
from detective_monkey.domain.common.identifiers import (
    CareerId,
    ProfileId,
    RecommendationId,
    StudentId,
)
from detective_monkey.domain.recommendation import (
    Dimension,
    DimensionScore,
    EvidenceCategory,
    Recommendation,
    RecommendationEvidence,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationWarning,
    WeightConfiguration,
)
from detective_monkey.domain.student import StudentIntelligenceProfile


def _career() -> Career:
    return Career(
        identity=CareerIdentity(
            id=CareerId.generate(),
            canonical_name="Data Scientist",
            slug="data-scientist",
        ),
        version=Version(1),
    )


def _profile() -> StudentIntelligenceProfile:
    return StudentIntelligenceProfile(
        id=ProfileId.generate(),
        student_id=StudentId.generate(),
        profile_version=Version(1),
    )


def _weights() -> WeightConfiguration:
    return WeightConfiguration(
        version=Version(1),
        weights=(
            (Dimension.SKILL, UnitInterval(0.5)),
            (Dimension.PSYCHOLOGICAL, UnitInterval(0.5)),
        ),
    )


def _recommendation(career_id: CareerId) -> Recommendation:
    return Recommendation(
        id=RecommendationId.generate(),
        career_id=career_id,
        overall_score=Score(82),
        confidence=Confidence.of(0.7),
        recommendation_version=Version(1),
        input_versions=VersionSet(),
        evidence=(RecommendationEvidence(EvidenceCategory.SKILL_ALIGNMENT, "Strong Python"),),
    )


def test_dimension_score_carries_confidence_and_evidence() -> None:
    """25 §6/§17, INV-02: a dimension score may carry its confidence + evidence."""
    ds = DimensionScore(
        dimension=Dimension.SKILL,
        score=Score(78),
        confidence=Confidence.of(0.8),
        evidence=(EvidenceId.generate(),),
    )
    assert ds.confidence is not None
    assert len(ds.evidence) == 1

    # Backward-compatible: still constructible with just dimension + score.
    bare = DimensionScore(Dimension.GOAL, Score(50))
    assert bare.confidence is None
    assert bare.evidence == ()


def test_recommendation_request_requires_at_least_one_career() -> None:
    """25 §19 Input: the engine needs candidate careers to consider."""
    with pytest.raises(ValueError):
        RecommendationRequest(
            profile=_profile(),
            careers=(),
            weights=_weights(),
        )


def test_recommendation_request_rejects_non_positive_candidate_limit() -> None:
    with pytest.raises(ValueError):
        RecommendationRequest(
            profile=_profile(),
            careers=(_career(),),
            weights=_weights(),
            candidate_limit=0,
        )


def test_recommendation_response_round_trips() -> None:
    """25 §19 Output: ranked recommendations + warnings travel together."""
    career = _career()
    response = RecommendationResponse(
        recommendations=(_recommendation(career.id),),
        warnings=(
            RecommendationWarning(
                code="low_profile_completeness",
                message="Profile based on a single assessment.",
            ),
        ),
    )
    assert len(response.recommendations) == 1
    assert response.warnings[0].code == "low_profile_completeness"
