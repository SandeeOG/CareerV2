"""Discovery loop (v3) — executable documentation.

Covers: deterministic calibration by age/class/ability/working style,
experiment design and skip rotation, reflection → experience evidence →
recalibration (with damping), evidence strength semantics, the full loop
through the demo backend, and SQLite persistence across a simulated restart.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from detective_monkey.application.seed import build_demo_backend
from detective_monkey.domain.common.identifiers import StudentId
from detective_monkey.engines.discovery import (
    COMPLETED,
    PROPOSED,
    DiscoveryEngine,
    Reflection,
    calibrate,
    evidence_strength,
)
from detective_monkey.engines.discovery.engine import (
    experiment_from_json,
    experiment_to_json,
)
from detective_monkey.engines.student_evidence import (
    AcademicRecord,
    EvidenceSubmission,
    OpenResponse,
    StudentEvidenceEngine,
    StudentGoalsInfo,
    StudentProfileInfo,
)
from detective_monkey.engines.student_evidence.schema import (
    profile_from_json,
    profile_to_json,
)
from detective_monkey.engines.student_evidence.scoring import StructuredAnswer


_EVIDENCE = StudentEvidenceEngine()


def _profile(student="s", grade="9", avg=75.0, hands=3, teamy=3, tech=4, people=3):
    return _EVIDENCE.build(EvidenceSubmission(
        student_id=StudentId(student),
        profile=StudentProfileInfo(name="T", grade=grade, country="India"),
        academic=(AcademicRecord("Mathematics", avg),),
        goals=StudentGoalsInfo(),
        structured_answers=(
            StructuredAnswer("int_tech", value=tech),
            StructuredAnswer("wrk_hands", value=hands),
            StructuredAnswer("wrk_team", value=teamy),
            StructuredAnswer("int_people", value=people),
            StructuredAnswer("per_analagain", value=4),
        ),
        open_responses=(),
    ))


class _Career:
    """Duck-typed knowledge profile for engine-level tests."""

    def __init__(self):
        self.id = "robotics-automation"
        self.name = "Robotics & Automation"
        self.industry = "technology-computing"
        self.tags = ("programming", "analytical")
        self.portfolio_ideas = ("a line-following robot",)
        self.projects = ("an obstacle-avoiding car",)
        self.youtube = ("RoboChannel",)
        self.books = ("Robot Basics",)
        self.courses = ("Intro to Robotics",)
        self.communities = ("r/robotics",)
        self.typical_employers = ("ISRO",)
        self.entrepreneurship = 0.4
        self.remote_work = 0.4
        self.government_opportunities = 0.5


# -- calibration: age, class, intelligence, working style ------------------------


def test_calibration_scales_with_grade():
    young = calibrate(_profile("a", grade="7"))
    old = calibrate(_profile("b", grade="12"))
    assert young.stage == "explorer" and old.stage == "specialist"
    assert young.minutes < old.minutes


def test_calibration_scales_with_ability():
    weak = calibrate(_profile("a", avg=35.0, tech=2), ("analytical_thinking",))
    strong = calibrate(_profile("b", avg=96.0, tech=5), ("analytical_thinking",))
    assert weak.tier < strong.tier
    assert weak.minutes < strong.minutes


def test_calibration_uses_age_when_grade_missing():
    profile = _EVIDENCE.build(EvidenceSubmission(
        student_id=StudentId("c"),
        profile=StudentProfileInfo(name="T", age=12),
        structured_answers=(StructuredAnswer("int_tech", value=3),)))
    assert calibrate(profile).stage == "explorer"  # age 12 ≈ grade 7


def test_calibration_always_explains_itself():
    cal = calibrate(_profile())
    assert len(cal.reasons) == 3
    assert all(r.strip() for r in cal.reasons)


def test_modality_follows_working_style():
    maker = calibrate(_profile("a", hands=5, teamy=2, people=2))
    social = calibrate(_profile("b", hands=1, teamy=5, people=5, tech=2))
    assert maker.modalities[0] == "build"
    assert social.modalities[0] in ("join", "talk")


# -- experiment design ---------------------------------------------------------


def test_design_is_deterministic_and_complete():
    profile = _profile()
    engine = DiscoveryEngine()
    a = engine.design(profile, _Career(), "x1", now=datetime.now(timezone.utc))
    b = engine.design(profile, _Career(), "x2", now=datetime.now(timezone.utc))
    assert (a.title, a.task, a.modality, a.minutes) == (b.title, b.task, b.modality, b.minutes)
    assert a.steps and a.brief and a.tests_features and a.calibration_reasons
    assert a.minutes >= 15
    assert a.status == PROPOSED


def test_skip_rotation_changes_the_task():
    profile = _profile(hands=5)
    engine = DiscoveryEngine()
    first = engine.design(profile, _Career(), "x1", attempt=0)
    second = engine.design(profile, _Career(), "x2", attempt=1)
    assert (first.modality, first.task) != (second.modality, second.task)


def test_brief_polish_is_validation_gated():
    class _BadLLM:  # tries to drop the career name / go multi-paragraph
        def generate(self, prompt):
            return "Do whatever!\n\nSeriously."
    engine = DiscoveryEngine(llm=_BadLLM())
    experiment = engine.design(_profile(), _Career(), "x1")
    assert "Robotics & Automation" in experiment.brief  # deterministic fallback


def test_experiment_json_round_trip():
    experiment = DiscoveryEngine().design(_profile(), _Career(), "x1")
    reflected = experiment_from_json(experiment_to_json(experiment))
    assert reflected == experiment


# -- reflection → evidence -------------------------------------------------------


def test_positive_reflection_raises_tested_features():
    profile = _profile()
    engine = DiscoveryEngine()
    experiment = engine.design(profile, _Career(), "x1")
    features = engine.reflection_features(
        experiment, Reflection(enjoyment=5, energy=5, would_do_again=5))
    for name in experiment.tests_features:
        assert features[name].score > 0.9
        assert features[name].evidence[0].startswith("Tried it:")


def test_negative_reflection_is_damped_not_teleporting():
    profile = _profile(tech=5)
    engine = DiscoveryEngine()
    experiment = engine.design(profile, _Career(), "x1")
    before = profile.feature("technical_interest").score
    features = engine.reflection_features(
        experiment, Reflection(enjoyment=1, energy=1, would_do_again=1))
    updated = _EVIDENCE.apply_experience(profile, features)
    after = updated.feature("technical_interest").score
    assert after < before                      # belief moved down…
    assert before - after <= 0.20 + 1e-9       # …but no more than the clamp


def test_enthusiastic_text_never_drags_a_feature_down():
    """The text says *which* features; the sliders say *how it felt*."""
    profile = _profile(tech=5)
    engine = DiscoveryEngine()
    experiment = engine.design(profile, _Career(), "x1")
    before = profile.feature("technical_interest").score
    features = engine.reflection_features(
        experiment,
        Reflection(enjoyment=5, energy=5, would_do_again=5,
                   text="I loved coding the robot, best afternoon ever."))
    updated = _EVIDENCE.apply_experience(profile, features)
    after = updated.feature("technical_interest").score
    # A perfect self-report may regress slightly toward observed evidence,
    # but enthusiasm must never meaningfully lower the feature.
    assert after >= before - 0.06
    assert after >= 0.9


def test_experience_becomes_a_tracked_source():
    profile = _profile()
    engine = DiscoveryEngine()
    experiment = engine.design(profile, _Career(), "x1")
    features = engine.reflection_features(
        experiment, Reflection(enjoyment=4, energy=4, would_do_again=4))
    updated = _EVIDENCE.apply_experience(profile, features)
    assert "experience" in updated.metadata.sources_used
    assert evidence_strength(profile, _Career()) == 0
    assert evidence_strength(updated, _Career()) > 0


# -- full loop through the demo backend --------------------------------------------


@pytest.fixture()
def backend():
    return build_demo_backend()


def _submit(backend, student="loop"):
    sid = StudentId(student)
    result = backend.evidence.submit(sid, {
        "profile": {"name": "Asha", "grade": "9", "country": "India"},
        "answers": [
            {"question_id": "int_tech", "value": 5},
            {"question_id": "int_free_time", "selected": ["build"]},
            {"question_id": "int_school_subjects", "selected": ["maths", "cs"]},
            {"question_id": "per_analagain", "value": 5},
            {"question_id": "wrk_hands", "value": 5},
        ],
        "open_answers": [],
    })
    assert result.success
    return sid


def test_full_discovery_cycle(backend):
    sid = _submit(backend)
    overview = backend.discovery.overview(sid)
    assert overview.success
    proposed = overview.data["proposed"]
    assert 1 <= len(proposed) <= 3
    assert all(p["why_this_task"] for p in proposed)      # always explainable

    target = proposed[0]
    assert backend.discovery.accept(sid, target["id"]).success

    done = backend.discovery.complete(sid, target["id"], {
        "enjoyment": 5, "energy": 4, "would_do_again": 5,
        "text": "Loved it, want more of this."})
    assert done.success
    diff = done.data
    # The tested hypothesis leads the diff.
    assert diff["career_moves"][0]["career"] == target["career_name"]
    assert diff["evidence_strength"]["after"] > diff["evidence_strength"]["before"]
    assert diff["momentum"]["cycles"] == 1
    assert diff["next_experiment"] is not None
    # Completing twice is rejected.
    again = backend.discovery.complete(sid, target["id"], {"enjoyment": 3, "energy": 3, "would_do_again": 3})
    assert not again.success


def test_skip_provides_a_replacement(backend):
    sid = _submit(backend, "skipper")
    target = backend.discovery.overview(sid).data["proposed"][0]
    result = backend.discovery.skip(sid, target["id"])
    assert result.success
    replacement = result.data["replacement"]
    assert replacement is not None
    assert replacement["career_id"] == target["career_id"]
    assert replacement["title"] != target["title"] or replacement["modality"] != target["modality"]


def test_untried_careers_cap_transferred_evidence(backend):
    sid = _submit(backend, "capper")
    target = backend.discovery.overview(sid).data["proposed"][0]
    backend.discovery.complete(sid, target["id"], {
        "enjoyment": 5, "energy": 5, "would_do_again": 5})
    rows = backend.discovery.hypotheses(sid).data["hypotheses"]
    for row in rows:
        if row["experiments_run"] == 0:
            assert row["evidence_strength"] <= 50


def test_experiments_require_ownership(backend):
    sid = _submit(backend, "owner")
    target = backend.discovery.overview(sid).data["proposed"][0]
    intruder = StudentId("intruder")
    assert not backend.discovery.accept(intruder, target["id"]).success
    assert not backend.discovery.complete(intruder, target["id"], {"enjoyment": 5, "energy": 5, "would_do_again": 5}).success


# -- persistence across restart -------------------------------------------------------


def test_profile_json_round_trip():
    profile = _profile("rt", grade="10")
    assert profile_from_json(profile_to_json(profile)) == profile


def test_sqlite_survives_restart():
    db = os.path.join(tempfile.mkdtemp(), "dm-test.db")
    first = build_demo_backend(db_path=db)
    sid = _submit(first, "persistent")
    target = first.discovery.overview(sid).data["proposed"][0]
    first.discovery.complete(sid, target["id"], {
        "enjoyment": 4, "energy": 4, "would_do_again": 4, "text": "Nice."})

    # A brand-new backend over the same file = a server restart.
    second = build_demo_backend(db_path=db)
    home = second.evidence.home(sid)          # lazy intelligence rebuild
    assert home.success
    assert home.data["momentum"]["cycles"] == 1
    overview = second.discovery.overview(sid)
    assert len(overview.data["completed"]) == 1
    assert overview.data["completed"][0]["reflection"]["enjoyment"] == 4
    # Recommendations work immediately after restart too.
    recs = second.intelligence.recommend(sid)
    assert recs.success and recs.data.cards
