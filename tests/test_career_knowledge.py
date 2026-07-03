"""Tests for the v1 Career Knowledge Base (prompts 38/39).

Covers: generated data integrity (16 industries, ~300 schema-valid profiles),
loader validation, repository search/filter/adapters, single-source-of-truth
backend composition, and the Explore Careers API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from detective_monkey.application import seed
from detective_monkey.knowledge.careers import (
    CareerKnowledgeLoader,
    CareerKnowledgeRepository,
    CareerSearchFilters,
)
from detective_monkey.knowledge.careers.loader import DATA_DIR
from detective_monkey.knowledge.careers.schema import validate_career_json


@pytest.fixture(scope="module")
def repo() -> CareerKnowledgeRepository:
    return CareerKnowledgeLoader().build_repository()


@pytest.fixture(scope="module")
def backend():
    return seed.build_demo_backend()


# ---------------------------------------------------------------------------
# Generated data integrity
# ---------------------------------------------------------------------------


def test_knowledge_base_size(repo):
    assert len(repo.industries()) == 16
    assert 250 <= repo.count() <= 350  # "approximately 300 broad career paths"
    assert repo.report.rejected == 0 and not repo.report.issues


def test_every_file_follows_the_canonical_schema():
    files = [p for p in DATA_DIR.glob("*.json") if p.name != "industries.json"]
    assert len(files) >= 250
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert validate_career_json(data) == [], path.name


def test_relationship_integrity_and_no_duplicates(repo):
    names = {p.name for p in repo.all_profiles()}
    ids = [p.id for p in repo.all_profiles()]
    assert len(ids) == len(set(ids))  # duplicate careers rejected
    for p in repo.all_profiles():
        assert p.related_careers, p.id
        for related in p.related_careers:
            assert related in names, f"{p.id} -> {related}"
        assert p.industry in {i.id for i in repo.industries()}


def test_schema_validator_rejects_broken_profiles(repo):
    good = json.loads(
        (DATA_DIR / "software_engineering.json").read_text(encoding="utf-8"))
    assert validate_career_json({**good, "salary_entry_lpa": 99,
                                 "salary_senior_lpa": 1})
    assert any("missing field" in i for i in validate_career_json(
        {k: v for k, v in good.items() if k != "faqs"}))
    assert any("duplicate tags" in i for i in validate_career_json(
        {**good, "tags": ["software", "software"]}))
    assert any("confidence" in i for i in validate_career_json(
        {**good, "confidence": 0.1}))


def test_loader_rejects_invalid_files(tmp_path: Path):
    (tmp_path / "industries.json").write_text('[{"id": "x", "name": "X", "description": "d"}]')
    (tmp_path / "broken.json").write_text("{not json")
    (tmp_path / "empty.json").write_text('{"id": "empty"}')
    profiles, industries, report = CareerKnowledgeLoader(tmp_path).load()
    assert profiles == () and len(industries) == 1
    assert report.rejected == 2 and len(report.issues) == 2


# ---------------------------------------------------------------------------
# Repository: browse, search, filters, relationships
# ---------------------------------------------------------------------------


def test_industry_navigation(repo):
    tech = repo.industry("technology-computing")
    assert tech is not None and tech.featured_careers
    careers = repo.careers_in("technology-computing")
    assert any(p.id == "software-engineering" for p in careers)
    assert all(p.industry == "technology-computing" for p in careers)


def test_get_by_id_and_by_name(repo):
    assert repo.get("software-engineering").name == "Software Engineering"
    assert repo.get("Software Engineering").id == "software-engineering"
    assert repo.get("nope") is None


def test_related_careers_resolve_to_profiles(repo):
    related = repo.related("software-engineering")
    assert related and all(r.id != "software-engineering" for r in related)


def test_search_by_name_interest_and_skill(repo):
    assert repo.search("software")[0].id == "software-engineering"
    assert any("data" in p.id for p in repo.search("machine learning statistics"))
    names = [p.name for p in repo.search("animals")]
    assert "Veterinary Science" in names


def test_filters(repo):
    for p in repo.search("", CareerSearchFilters(remote=True)):
        assert p.remote_work >= 0.6
    for p in repo.search("", CareerSearchFilters(ai_safe=True)):
        assert p.automation_risk <= 0.3
    no_code = repo.search("", CareerSearchFilters(requires_programming=False))
    assert no_code and all(
        "programming" not in " ".join(p.tags + p.core_skills).lower()
        for p in no_code)
    gov = repo.search("", CareerSearchFilters(government=True, industry="defence-security"))
    assert gov and all(p.industry == "defence-security" for p in gov)


# ---------------------------------------------------------------------------
# Single source of truth: adapters + backend composition
# ---------------------------------------------------------------------------


def test_adapters_cover_every_profile(repo):
    aggregates = repo.career_aggregates()
    insights = repo.insights()
    assert len(aggregates) == repo.count() == len(insights)
    ids = {a.id.value for a in aggregates}
    assert ids == set(insights)
    sample = insights["software-engineering"]
    assert sample.roadmap and sample.salary_senior > sample.salary_entry
    # Insight related-career ids resolve back into the same knowledge base.
    for rid in sample.related_careers:
        assert repo.get(rid) is not None


def test_backend_is_powered_by_the_knowledge_base(backend):
    assert backend.career_knowledge is not None
    assert len(backend.careers.list_all()) == backend.career_knowledge.count()
    assert set(backend.career_insights) == {
        p.id for p in backend.career_knowledge.all_profiles()}
    # Career profiles are first-class knowledge entities in the platform graph.
    node = backend.knowledge_platform.traversal.find_by_name("Software Engineering")
    assert node is not None and node.node_type.value == "career"
    industries = backend.knowledge_platform.traversal.neighbours(
        node.id.value)
    assert industries  # BELONGS_TO industry / REQUIRES skills edges exist


def test_full_journey_runs_on_knowledge_careers(backend):
    from detective_monkey.domain.common.identifiers import StudentId
    from detective_monkey.engines.assessment import (
        AssessmentInput, AssessmentSubmission, ItemResponse,
    )

    defn = seed.default_assessment_definition()
    qs = [q for s in defn.sections for q in s.questions]
    answers = {"q1": 5, "q2": 1, "q9": 5, "q10": 1}
    sub = AssessmentSubmission(
        StudentId("k"), defn.id, defn.version,
        tuple(ItemResponse(q.id, answers.get(q.id, 3), 1400) for q in qs))
    result = backend.intelligence.build_from_assessment(AssessmentInput(defn, sub))
    assert result.success

    recs = backend.intelligence.recommend(StudentId("k"))
    assert recs.success and len(recs.data.cards) == backend.career_knowledge.count()
    top = recs.data.cards[0]
    profile = backend.career_knowledge.get(top.career_id)
    assert profile is not None  # every recommendation links to a full profile
    assert top.summary == profile.student_summary
    assert "LPA" in top.salary_range or "Variable" in top.salary_range

    detail = backend.intelligence.career_detail(StudentId("k"), top.career_id)
    assert detail.success and detail.data.roadmap.steps


# ---------------------------------------------------------------------------
# Explore Careers API
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client(backend):
    fastapi = pytest.importorskip("fastapi")  # noqa: F841 - optional adapter
    from fastapi.testclient import TestClient
    from detective_monkey.interfaces.rest.app import create_app
    return TestClient(create_app(backend))


def test_api_lists_16_industries(client):
    body = client.get("/api/v1/careers/industries").json()
    assert body["success"] and len(body["data"]) == 16
    assert all(i["career_count"] > 0 for i in body["data"])


def test_api_industry_and_profile_pages(client):
    body = client.get("/api/v1/careers/industries/healthcare-medicine").json()
    assert body["success"] and body["data"]["careers"]
    career_id = body["data"]["careers"][0]["id"]
    profile = client.get(f"/api/v1/careers/{career_id}").json()
    assert profile["success"]
    data = profile["data"]
    assert data["faqs"] and data["related_profiles"] and data["industry_name"]
    assert client.get("/api/v1/careers/not-a-career").status_code == 404


def test_api_search_and_filters(client):
    body = client.get("/api/v1/careers/search", params={"q": "design"}).json()
    assert body["success"] and body["data"]
    body = client.get("/api/v1/careers/search",
                      params={"remote": "true", "ai_safe": "true"}).json()
    assert body["success"]
    for card in body["data"]:
        assert card["remote_work"] >= 0.6 and card["automation_risk"] <= 0.3


def test_coach_retrieves_career_knowledge(client):
    body = client.post("/api/v1/conversations",
                       json={"message": "tell me about software engineering"}).json()
    assert body["success"]
    assert "software" in body["data"]["response"].lower()
