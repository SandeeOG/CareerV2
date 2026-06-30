"""Tests that the documented domain invariants are enforced in code.

Each test cites the design document and invariant it protects.
"""

from __future__ import annotations

import dataclasses

import pytest

from detective_monkey.domain.common import (
    Confidence,
    Evidence,
    EvidenceId,
    Provenance,
    Score,
    SourceType,
    Version,
    VersionSet,
)
from detective_monkey.domain.common.identifiers import (
    CareerId,
    ProfileId,
    RecommendationId,
    SkillId,
    StudentId,
)
from detective_monkey.domain.knowledge_graph import Edge, EdgeDirection, RelationshipType
from detective_monkey.domain.knowledge_graph.node import NodeId
from detective_monkey.domain.recommendation import (
    EvidenceCategory,
    Recommendation,
    RecommendationEvidence,
    WeightConfiguration,
)
from detective_monkey.domain.recommendation.dimensions import Dimension
from detective_monkey.domain.recommendation.weights import WeightConfiguration as WC
from detective_monkey.domain.skills import StudentSkill
from detective_monkey.domain.skills.student_skill import ProficiencyLevel
from detective_monkey.domain.student import (
    DerivedFeature,
    StudentIntelligenceProfile,
)


def _evidence() -> Evidence:
    return Evidence(
        id=EvidenceId.generate(),
        subject="analytical_reasoning",
        provenance=Provenance(SourceType.ASSESSMENT),
        confidence=Confidence.of(0.8),
    )


def test_evidence_is_immutable() -> None:
    """18 §23 INV-01: Evidence is immutable."""
    ev = _evidence()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.subject = "changed"  # type: ignore[misc]


def test_derived_feature_requires_evidence() -> None:
    """11 §13 INV-03: derived features must reference evidence."""
    with pytest.raises(ValueError):
        DerivedFeature(
            name="programming_affinity",
            score=Score(80),
            confidence=Confidence.of(0.7),
            evidence=(),
        )
    # With evidence it is valid.
    DerivedFeature(
        name="programming_affinity",
        score=Score(80),
        confidence=Confidence.of(0.7),
        evidence=(EvidenceId.generate(),),
    )


def test_student_skill_requires_evidence_above_baseline() -> None:
    """13 §11 INV-04: a known student skill requires evidence."""
    with pytest.raises(ValueError):
        StudentSkill(
            student_id=StudentId.generate(),
            skill_id=SkillId.generate(),
            proficiency=ProficiencyLevel.ADVANCED,
            confidence=Confidence.of(0.6),
            evidence=(),
        )


def test_sip_is_immutable() -> None:
    """10 §7 / 11 §18: the SIP is immutable for a given version."""
    sip = StudentIntelligenceProfile(
        id=ProfileId.generate(),
        student_id=StudentId.generate(),
        profile_version=Version(1),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        sip.profile_version = Version(2)  # type: ignore[misc]


def test_edge_forbids_self_loops() -> None:
    """17 §9/§20: a relationship cannot connect a node to itself."""
    from detective_monkey.domain.common.identifiers import EdgeId

    node = NodeId.generate()
    with pytest.raises(ValueError):
        Edge(
            id=EdgeId.generate(),
            edge_type=RelationshipType.RELATED_TO,
            source=node,
            target=node,
            version=Version(1),
            direction=EdgeDirection.UNDIRECTED,
        )


def test_weight_configuration_must_sum_to_one() -> None:
    """16 §8/§9: weights are configurable and must form a valid distribution."""
    with pytest.raises(ValueError):
        WC(
            version=Version(1),
            weights=(
                (Dimension.SKILL, __unit(0.5)),
                (Dimension.PSYCHOLOGICAL, __unit(0.2)),
            ),
        )
    WC(
        version=Version(1),
        weights=(
            (Dimension.SKILL, __unit(0.5)),
            (Dimension.PSYCHOLOGICAL, __unit(0.5)),
        ),
    )


def __unit(v: float):
    from detective_monkey.domain.common import UnitInterval

    return UnitInterval(v)


def test_recommendation_requires_evidence() -> None:
    """16 §20 INV-04: recommendations always include evidence."""
    with pytest.raises(ValueError):
        Recommendation(
            id=RecommendationId.generate(),
            career_id=CareerId.generate(),
            overall_score=Score(82),
            confidence=Confidence.of(0.7),
            recommendation_version=Version(1),
            input_versions=VersionSet(),
            evidence=(),
        )


def test_recommendation_value_equality_is_deterministic() -> None:
    """16 §20 INV-08: identical inputs produce identical outputs.

    Built as a pure value object, two recommendations with identical fields are
    equal — the foundation for reproducibility.
    """
    rid = RecommendationId.generate()
    cid = CareerId.generate()
    ev = (RecommendationEvidence(EvidenceCategory.SKILL_ALIGNMENT, "Strong Python"),)
    common = dict(
        id=rid,
        career_id=cid,
        overall_score=Score(82),
        confidence=Confidence.of(0.7),
        recommendation_version=Version(1),
        input_versions=VersionSet(),
        evidence=ev,
        created_at=_fixed_time(),
    )
    assert Recommendation(**common) == Recommendation(**common)


def _fixed_time():
    from datetime import datetime, timezone

    return datetime(2026, 1, 1, tzinfo=timezone.utc)
