"""Mentor reasoning unit tests (engines/intelligence/mentor.py)."""

from __future__ import annotations

from detective_monkey.application import seed
from detective_monkey.contracts import EngineRequest, IntelligenceContext
from detective_monkey.domain.common.identifiers import StudentId
from detective_monkey.domain.student.student import Student
from detective_monkey.engines.assessment import (
    AssessmentEngine, AssessmentInput, AssessmentSubmission, ItemResponse,
)
from detective_monkey.engines.intelligence import IntelligenceEngine, mentor, rank_careers

_ANALYTICAL = {"q1": 5, "q2": 1, "q9": 5, "q10": 1}


def _profile():
    defn = seed.default_assessment_definition()
    qs = [q for s in defn.sections for q in s.questions]
    sub = AssessmentSubmission(StudentId("t"), defn.id, defn.version,
                               tuple(ItemResponse(q.id, _ANALYTICAL.get(q.id, 3), 1400) for q in qs))
    ares = AssessmentEngine().execute(EngineRequest(IntelligenceContext(), AssessmentInput(defn, sub))).result
    return IntelligenceEngine().build(ares, Student(id=StudentId("t")))


def test_readiness_and_levels():
    r = mentor.career_readiness(_profile())
    assert 0 <= r.score <= 100
    assert r.level in ("Emerging", "Developing", "Strong", "Excellent")
    assert r.increases and r.decreases


def test_opportunity_and_today_and_summary():
    p = _profile()
    matches = rank_careers(p, seed.demo_careers())
    insights = seed.demo_career_insights()
    opp = mentor.biggest_opportunity(matches, insights)
    assert opp.title and opp.employability_gain > 0
    action = mentor.todays_recommendation(p, opp)
    assert action.title
    summary = mentor.ai_summary(p, matches, opp)
    assert matches[0].name in summary  # personalized to the student's top match


def test_skill_gap_projects_higher():
    p = _profile()
    matches = rank_careers(p, seed.demo_careers())
    insights = seed.demo_career_insights()
    m = matches[0]
    gap = mentor.skill_gap(p, m, insights[m.career_id])
    assert gap.projected_compatibility >= gap.current_compatibility


def test_roadmap_and_compare():
    p = _profile()
    insights = seed.demo_career_insights()
    rm = mentor.roadmap(insights["c_ds"], "Data Scientist")
    assert rm.steps[0].status == "in_progress"
    assert any(s.title == "Portfolio" for s in rm.steps)
    matches = rank_careers(p, seed.demo_careers())
    ma = next(m for m in matches if m.career_id == "c_ds")
    mb = next(m for m in matches if m.career_id == "c_ux")
    cmp = mentor.compare(p, "Data Scientist", insights["c_ds"], ma,
                         "UX Designer", insights["c_ux"], mb)
    assert cmp.rows and "match" in cmp.recommendation.lower()


def test_suggested_questions_are_contextual():
    p = _profile()
    matches = rank_careers(p, seed.demo_careers())
    qs = mentor.suggested_questions(p, matches)
    assert qs and any(matches[0].name in q for q in qs)
