"""Full HTTP journey test — Phase 2 AI mentor experience.

Skipped when FastAPI is not installed (optional dependency).
"""

from __future__ import annotations

import importlib.util

import pytest

_HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI not installed")


def _client():
    from fastapi.testclient import TestClient
    from detective_monkey.interfaces.rest.app import create_app
    return TestClient(create_app())


def test_full_mentor_journey():
    client = _client()

    assert client.get("/").status_code == 200
    assert client.get("/api/v1/health").json()["data"]["status"] == "healthy"

    defn = client.get("/api/v1/assessments/default").json()["data"]
    questions = [q for s in defn["sections"] for q in s["questions"]]
    sid = "ada-test"

    # Assessment -> Intelligence profile (Analysis step)
    answers = [{"question_id": q["id"], "value": 4, "duration_ms": 1500} for q in questions]
    assert client.post(f"/api/v1/students/{sid}/assessment", json={"answers": answers}).json()["success"]

    # Epic 1 — AI dashboard
    dash = client.get(f"/api/v1/students/{sid}/dashboard").json()
    assert dash["success"], dash["errors"]
    d = dash["data"]
    assert d["ai_summary"] and 0 <= d["readiness"]["score"] <= 100
    assert d["strengths"] and d["opportunity"]["title"] and d["todays_action"]["title"]
    assert d["suggested_questions"]

    # Epic 2 — premium recommendation cards
    recs = client.post(f"/api/v1/students/{sid}/recommendations", json={}).json()
    assert recs["success"]
    cards = recs["data"]["cards"]
    assert cards
    top = cards[0]
    for field in ("name", "score", "match_explanation", "salary_range", "future_demand",
                  "automation_risk", "skill_gaps", "estimated_learning_weeks",
                  "next_actions", "evidence"):
        assert field in top
    cid = top["career_id"]

    # Epic 3 — career detail (personalized)
    detail = client.get(f"/api/v1/students/{sid}/careers/{cid}").json()["data"]
    assert detail["personal_note"] and detail["roadmap"]["steps"]

    # Epic 6 — roadmap
    rm = client.get(f"/api/v1/students/{sid}/careers/{cid}/roadmap").json()["data"]
    assert rm["steps"][0]["status"] == "in_progress"

    # Epic 7 — skill gap
    gap = client.get(f"/api/v1/students/{sid}/careers/{cid}/skill-gap").json()["data"]
    assert gap["projected_compatibility"] >= gap["current_compatibility"]

    # Epic 8 — comparison (any two recommended knowledge careers)
    cmp = client.get(f"/api/v1/students/{sid}/compare",
                     params={"a": cid, "b": cards[1]["career_id"]}).json()["data"]
    assert cmp["rows"] and cmp["recommendation"]

    # 38/39 — every recommendation links to its full Career Profile page
    profile = client.get(f"/api/v1/careers/{cid}").json()
    assert profile["success"] and profile["data"]["id"] == cid
    assert profile["data"]["related_profiles"]

    # Epic 9 — downloadable report (HTML)
    report = client.get(f"/api/v1/students/{sid}/report")
    assert report.status_code == 200
    assert "AI Career Report" in report.text

    # Epic 4/5 — context-aware coach + suggestions
    chat = client.post("/api/v1/conversations",
                       json={"message": "Should I learn Python?", "student_id": sid}).json()
    assert chat["success"]
    assert chat["data"]["response"].strip()
    assert chat["data"]["suggestions"]


def test_dashboard_missing_profile_is_404():
    client = _client()
    resp = client.get("/api/v1/students/nobody/dashboard")
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "NOT_FOUND"
