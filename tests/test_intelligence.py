"""Intelligence Engine v1 unit tests (engines/intelligence/)."""

from __future__ import annotations

import dataclasses

import pytest

from detective_monkey.application import seed
from detective_monkey.contracts import EngineRequest, IntelligenceContext
from detective_monkey.domain.common.identifiers import StudentId
from detective_monkey.domain.student.student import Student
from detective_monkey.engines.assessment import (
    AssessmentEngine, AssessmentInput, AssessmentSubmission, ItemResponse,
)
from detective_monkey.engines.intelligence import (
    ConversationContext, IntelligenceEngine, StudentIntelligenceProfile, rank_careers,
)


def _assessment_result(values: dict[str, int]):
    defn = seed.default_assessment_definition()
    qs = [q for s in defn.sections for q in s.questions]
    sub = AssessmentSubmission(
        StudentId("t"), defn.id, defn.version,
        tuple(ItemResponse(q.id, values.get(q.id, 3), 1400) for q in qs))
    return AssessmentEngine().execute(EngineRequest(IntelligenceContext(), AssessmentInput(defn, sub))).result


# A coherent "analytical + curious" student.
_ANALYTICAL = {"q1": 5, "q2": 1, "q9": 5, "q10": 1}


def test_profile_is_immutable_and_evidence_backed():
    ares = _assessment_result(_ANALYTICAL)
    profile = IntelligenceEngine().build(ares, Student(id=StudentId("t")))
    assert isinstance(profile, StudentIntelligenceProfile)
    assert 0.0 <= profile.confidence <= 1.0
    assert profile.strengths and profile.strengths[0].evidence  # every trait has evidence
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.confidence = 0.1  # type: ignore[misc]


def test_signals_drive_sensible_interests():
    ares = _assessment_result(_ANALYTICAL)
    profile = IntelligenceEngine().build(
        ares, Student(id=StudentId("t")),
        conversation=ConversationContext(("I love python and data",)))
    top_interest = profile.top_interests(1)[0].name
    assert top_interest in ("Research & Science", "Programming & Technology")
    assert profile.skill_vector.get("technical") >= 0.7  # conversation boosted technical


def test_ranking_prefers_matching_careers():
    ares = _assessment_result(_ANALYTICAL)
    profile = IntelligenceEngine().build(ares, Student(id=StudentId("t")))
    recs = rank_careers(profile, seed.demo_careers())
    assert recs
    top = recs[0]
    # Analytical/curious profile should top with Data/Research, above UX/PM.
    assert top.career_id in ("c_ds", "c_rs")
    assert top.reasons and top.evidence
    ux = next(r for r in recs if r.career_id == "c_ux")
    assert top.score >= ux.score


def test_determinism():
    a1 = _assessment_result(_ANALYTICAL)
    a2 = _assessment_result(_ANALYTICAL)
    p1 = IntelligenceEngine().build(a1, Student(id=StudentId("t")))
    p2 = IntelligenceEngine().build(a2, Student(id=StudentId("t")))
    r1 = [(r.career_id, r.score) for r in rank_careers(p1, seed.demo_careers())]
    r2 = [(r.career_id, r.score) for r in rank_careers(p2, seed.demo_careers())]
    assert r1 == r2


def test_build_is_the_only_public_method():
    public = [m for m in vars(IntelligenceEngine).keys()
              if not m.startswith("_") and callable(getattr(IntelligenceEngine, m))]
    assert public == ["build"]
