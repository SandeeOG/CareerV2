"""Student Evidence Engine V1 — executable documentation of the spec.

Covers: assessment definition integrity, deterministic structured scoring,
AI-extraction validation + retry + fallback, graceful missing-data handling,
human validation, the Career Pulse, the Intelligence-Engine bridge and the
full evidence → recommendation journey through the demo backend.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from detective_monkey.application.seed import build_demo_backend
from detective_monkey.domain.common.identifiers import StudentId
from detective_monkey.engines.student_evidence import (
    CAREER_PULSE,
    EVIDENCE_ASSESSMENT,
    FEATURE_NAMES,
    AcademicRecord,
    EvidenceSubmission,
    ExtractionValidationError,
    OpenResponse,
    StructuredAnswer,
    StudentEvidenceEngine,
    StudentGoalsInfo,
    StudentProfileInfo,
    extract_with_ai,
    heuristic_extraction,
    parse_and_validate,
    score_structured,
    to_assessment_result,
)
from detective_monkey.engines.student_evidence.affinity import career_affinity
from detective_monkey.engines.student_evidence.definitions import LIKERT, MULTI_CHOICE, OPEN


# -- definition integrity ------------------------------------------------------


def test_assessment_shape_matches_spec():
    # 40-60 questions, six conversational sections, ~10 open-ended.
    total = len(EVIDENCE_ASSESSMENT.questions())
    assert 40 <= total <= 60
    assert len(EVIDENCE_ASSESSMENT.sections) == 6
    assert len(EVIDENCE_ASSESSMENT.structured_questions()) >= 20
    assert len(EVIDENCE_ASSESSMENT.open_questions()) == 10
    section_ids = [s.id for s in EVIDENCE_ASSESSMENT.sections]
    assert section_ids == ["interests", "personality", "work_preferences",
                           "career_values", "strengths", "aspirations"]


def test_career_pulse_is_lightweight():
    assert len(CAREER_PULSE.questions()) <= 10


def test_all_question_features_are_canonical():
    for q in list(EVIDENCE_ASSESSMENT.questions()) + list(CAREER_PULSE.questions()):
        for feature, weight in q.features:
            assert feature in FEATURE_NAMES, f"{q.id} references unknown '{feature}'"
            assert 0 < weight <= 1.0
        for option in q.options:
            for feature, value in option.features:
                assert feature in FEATURE_NAMES, f"{q.id}/{option.id}: '{feature}'"
                assert 0 <= value <= 1.0


def test_question_ids_are_unique():
    ids = [q.id for q in EVIDENCE_ASSESSMENT.questions()]
    assert len(ids) == len(set(ids))


# -- structured scoring ----------------------------------------------------------


def test_structured_scoring_is_deterministic_and_bounded():
    answers = (
        StructuredAnswer("int_tech", value=5),
        StructuredAnswer("per_instinct", value=1),        # reverse-scored
        StructuredAnswer("int_free_time", selected=("build",)),
        StructuredAnswer("int_school_subjects", selected=("maths", "cs")),
    )
    a = score_structured(EVIDENCE_ASSESSMENT, answers)
    b = score_structured(EVIDENCE_ASSESSMENT, answers)
    assert a.keys() == b.keys()
    for name, feat in a.items():
        assert name in FEATURE_NAMES
        assert 0.0 <= feat.score <= 1.0
        assert 0.0 <= feat.confidence <= 1.0
        assert feat.evidence  # every feature carries evidence
        assert feat.score == b[name].score

    # Reverse scoring: disagreeing with "I go with my gut" supports analysis.
    assert a["analytical_thinking"].score > 0.7
    assert a["technical_interest"].score > 0.8


def test_unknown_and_open_answers_are_ignored_by_scoring():
    answers = (StructuredAnswer("nonexistent", value=5),
               StructuredAnswer("int_open_subject", value=3))
    assert score_structured(EVIDENCE_ASSESSMENT, answers) == {}


# -- AI extraction: validation, retry, fallback ------------------------------------


def test_parse_and_validate_accepts_canonical_json_with_fences():
    raw = "```json\n" + json.dumps({
        "technical_interest": {"score": 0.9, "confidence": 0.8,
                               "evidence": ["builds Python games"]}
    }) + "\n```"
    features = parse_and_validate(raw)
    assert features["technical_interest"].score == 0.9


@pytest.mark.parametrize("bad", [
    "",                                                        # empty
    "not json at all",                                         # no object
    json.dumps({"flying": {"score": .5, "confidence": .5, "evidence": ["x"]}}),   # unknown feature
    json.dumps({"creativity": {"score": 1.5, "confidence": .5, "evidence": ["x"]}}),  # score range
    json.dumps({"creativity": {"score": .5, "confidence": -1, "evidence": ["x"]}}),   # confidence range
    json.dumps({"creativity": {"score": .5, "confidence": .5, "evidence": []}}),      # no evidence
])
def test_parse_and_validate_rejects_schema_violations(bad):
    with pytest.raises(ExtractionValidationError):
        parse_and_validate(bad)


class _FlakyLLM:
    """Fails validation once, then returns valid JSON — exercises the retry."""

    def __init__(self):
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        if self.calls == 1:
            return "sorry, here is prose instead of JSON"
        return json.dumps({"curiosity": {"score": 0.8, "confidence": 0.7,
                                         "evidence": ["asks why constantly"]}})


def test_extraction_retries_and_never_stores_invalid_output():
    llm = _FlakyLLM()
    responses = (OpenResponse("q", "prompt", "I always ask why things work."),)
    features = extract_with_ai(llm, responses)
    assert llm.calls == 2
    assert features is not None and "curiosity" in features


def test_extraction_returns_none_when_provider_always_invalid():
    class _Bad:
        def generate(self, prompt):
            return "{ not json"
    assert extract_with_ai(_Bad(), (OpenResponse("q", "p", "text"),)) is None


def test_heuristic_fallback_is_deterministic_and_grounded():
    responses = (OpenResponse("q1", "p", "I love coding robots in Python and doing science experiments."),)
    a, b = heuristic_extraction(responses), heuristic_extraction(responses)
    assert a.keys() == b.keys()
    assert "technical_interest" in a
    assert all(f.evidence for f in a.values())


# -- engine: profile assembly + missing data ---------------------------------------


def _full_submission(student="s1") -> EvidenceSubmission:
    return EvidenceSubmission(
        student_id=StudentId(student),
        profile=StudentProfileInfo(name="Asha", grade="10", country="India"),
        academic=(AcademicRecord("Mathematics", 92, "improving"),),
        goals=StudentGoalsInfo(dream_career="Robotics Engineer",
                               entrepreneurship_interest="maybe",
                               willing_to_relocate="yes",
                               preferred_country="Germany"),
        structured_answers=(
            StructuredAnswer("int_tech", value=5),
            StructuredAnswer("int_free_time", selected=("build",)),
            StructuredAnswer("per_analagain", value=5),
        ),
        open_responses=(
            OpenResponse("int_open_subject", "?", "I build apps and love math puzzles."),
        ),
    )


def test_engine_builds_profile_from_all_four_sources():
    profile = StudentEvidenceEngine().build(_full_submission())
    assert set(profile.metadata.sources_used) == {"profile", "assessment", "academic", "goals"}
    names = {k for k, _ in profile.extracted_features}
    assert names <= set(FEATURE_NAMES)
    # Goals contribute — but as evidence, not overrides.
    assert profile.feature("relocation_preference") is not None
    assert profile.feature("career_confidence") is not None
    # Everything carries score/confidence/evidence in range.
    for _, feat in profile.extracted_features:
        assert 0 <= feat.score <= 1 and 0 <= feat.confidence <= 1 and feat.evidence


def test_missing_sources_never_block_the_profile():
    minimal = EvidenceSubmission(
        student_id=StudentId("s2"),
        structured_answers=(StructuredAnswer("int_tech", value=4),),
    )
    profile = StudentEvidenceEngine().build(minimal)
    assert "academic" not in profile.metadata.sources_used
    assert "goals" not in profile.metadata.sources_used
    assert profile.feature("technical_interest") is not None
    # Bridge still yields usable evidence for the Intelligence Engine.
    result = to_assessment_result(profile)
    assert result.evidence  # never empty, never fabricated beyond the sources


def test_multiple_sources_raise_confidence_over_single_source():
    engine = StudentEvidenceEngine()
    single = engine.build(EvidenceSubmission(
        student_id=StudentId("a"),
        structured_answers=(StructuredAnswer("int_tech", value=5),)))
    multi = engine.build(_full_submission("b"))
    assert (multi.feature("technical_interest").confidence
            > single.feature("technical_interest").confidence)


# -- human validation ----------------------------------------------------------------


def test_validation_softens_inaccurate_features_and_records_verdict():
    engine = StudentEvidenceEngine()
    profile = engine.build(_full_submission())
    before = profile.feature("technical_interest")
    updated = engine.apply_validation(profile, "partially", ("technical_interest",))
    after = updated.feature("technical_interest")
    assert updated.metadata.validation_status == "partially"
    assert after.confidence < before.confidence
    assert abs(after.score - 0.5) < abs(before.score - 0.5)  # pulled toward neutral
    assert "Student marked this as not accurate." in after.evidence


def test_yes_verdict_boosts_confidence():
    engine = StudentEvidenceEngine()
    profile = engine.build(_full_submission())
    updated = engine.apply_validation(profile, "yes")
    assert (updated.feature("technical_interest").confidence
            >= profile.feature("technical_interest").confidence)


# -- Career Pulse -----------------------------------------------------------------------


def test_pulse_due_after_six_months_only():
    engine = StudentEvidenceEngine()
    profile = engine.build(_full_submission())
    now = datetime.now(timezone.utc)
    assert not engine.pulse_due(profile, now)
    assert engine.pulse_due(profile, now + timedelta(days=183))


def test_pulse_updates_touched_features_and_goals():
    engine = StudentEvidenceEngine()
    profile = engine.build(_full_submission())
    before = profile.feature("technical_interest").score
    updated = engine.apply_pulse(
        profile,
        (StructuredAnswer("pls_tech", value=1),),  # interest dropped
        (OpenResponse("pls_open_goal", "?", "Game Designer"),),
    )
    assert updated.feature("technical_interest").score < before
    assert updated.goals.dream_career == "Game Designer"
    assert updated.metadata.last_pulse_at
    # Untouched features survive.
    assert updated.feature("analytical_thinking") is not None


# -- bridge to the Intelligence Engine -----------------------------------------------------


def test_bridge_produces_construct_observations():
    profile = StudentEvidenceEngine().build(_full_submission())
    result = to_assessment_result(profile)
    for evidence in result.evidence:
        assert evidence.metadata.get("kind") == "construct_observation"
        assert 0.0 <= float(evidence.metadata.get("value")) <= 100.0
    assert 0.0 <= result.quality.completion <= 1.0


# -- evidence → career affinity ---------------------------------------------------------


class _FakeCareer:
    def __init__(self, industry, tags=(), name=""):
        self.id = name or industry
        self.industry = industry
        self.tags = tags
        self.name = name
        self.entrepreneurship = 0.2
        self.remote_work = 0.5
        self.government_opportunities = 0.3


def test_affinity_prefers_evidence_aligned_industries():
    profile = StudentEvidenceEngine().build(_full_submission())  # techy student
    tech = career_affinity(profile, _FakeCareer("technology-computing", ("programming", "analytical")))
    social = career_affinity(profile, _FakeCareer("social-impact", ("care", "empathy")))
    assert tech > social


# -- full journey through the demo backend ------------------------------------------------


@pytest.fixture(scope="module")
def backend():
    return build_demo_backend()


def _submit(backend, student, answers, opens):
    return backend.evidence.submit(StudentId(student), {
        "profile": {"name": student.title(), "grade": "10", "country": "India"},
        "goals": {},
        "answers": answers,
        "open_answers": opens,
    })


def test_full_evidence_journey(backend):
    sid = StudentId("journey-1")
    result = backend.evidence.submit(sid, {
        "profile": {"name": "Asha", "grade": "10", "school": "DPS", "country": "India"},
        "goals": {"dream_career": "Robotics Engineer", "willing_to_relocate": "yes"},
        "academic": [{"subject": "Mathematics", "average_score": 92}],
        "answers": [
            {"question_id": "int_tech", "value": 5},
            {"question_id": "int_free_time", "selected": ["build"]},
            {"question_id": "per_analagain", "value": 5},
            {"question_id": "str_role", "selected": ["tech"]},
        ],
        "open_answers": [
            {"question_id": "int_open_subject", "text": "I build robots and code in Python."}],
    })
    assert result.success
    assert result.data["validation"]["qualities"]  # human-in-the-loop view

    home = backend.evidence.home(sid)
    assert home.success
    assert home.data["welcome"]["name"] == "Asha"
    assert home.data["matches"], "top matches must be present"
    assert home.data["growth"]["percent"] > 0
    assert home.data["insight"]["title"]

    # Validation feeds straight back into the stored profile.
    validated = backend.evidence.validate(sid, "yes", ())
    assert validated.success and validated.data["validation_status"] == "yes"

    # Evidence profile is retrievable as the single source of truth.
    evidence = backend.evidence.evidence(sid)
    assert evidence.success
    assert evidence.data["extracted_features"]
    assert evidence.data["metadata"]["sources_used"]


def test_home_is_not_found_before_any_evidence(backend):
    missing = backend.evidence.home(StudentId("nobody"))
    assert not missing.success
    assert missing.errors[0].code.value == "NOT_FOUND"


def test_contrasting_students_get_different_matches(backend):
    tech = _submit(backend, "techie", [
        {"question_id": "int_tech", "value": 5},
        {"question_id": "int_art", "value": 1},
        {"question_id": "int_people", "value": 2},
        {"question_id": "int_free_time", "selected": ["build"]},
        {"question_id": "int_school_subjects", "selected": ["maths", "cs"]},
        {"question_id": "per_analagain", "value": 5},
        {"question_id": "str_role", "selected": ["tech"]},
        {"question_id": "asp_tenyears", "selected": ["builder"]},
    ], [{"question_id": "int_open_subject", "text": "I love coding and robotics."}])
    creative = _submit(backend, "artist", [
        {"question_id": "int_tech", "value": 1},
        {"question_id": "int_art", "value": 5},
        {"question_id": "int_people", "value": 5},
        {"question_id": "int_free_time", "selected": ["create"]},
        {"question_id": "int_school_subjects", "selected": ["arts", "lang"]},
        {"question_id": "per_ideas", "value": 5},
        {"question_id": "str_role", "selected": ["design"]},
        {"question_id": "asp_tenyears", "selected": ["creator"]},
    ], [{"question_id": "int_open_subject", "text": "I love painting, design and film."}])
    assert tech.success and creative.success

    top_tech = [m["name"] for m in backend.evidence.home(StudentId("techie")).data["matches"]]
    top_creative = [m["name"] for m in backend.evidence.home(StudentId("artist")).data["matches"]]
    assert top_tech != top_creative
