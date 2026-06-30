"""Full HTTP journey test (P4 API + P5 served SPA + seeded backend).

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


def test_full_http_journey():
    client = _client()

    # Static SPA is served at root.
    root = client.get("/")
    assert root.status_code == 200
    assert "Detective Monkey" in root.text

    # Health
    assert client.get("/api/v1/health").json()["data"]["status"] == "healthy"

    # Assessment definition
    defn = client.get("/api/v1/assessments/default").json()
    assert defn["success"]
    questions = [q for s in defn["data"]["sections"] for q in s["questions"]]
    assert len(questions) >= 6

    sid = "ada-test"

    # Submit assessment (answer every question) -> profile is built (Analysis step)
    answers = [{"question_id": q["id"], "value": 4, "duration_ms": 1500} for q in questions]
    prof = client.post(f"/api/v1/students/{sid}/assessment", json={"answers": answers}).json()
    assert prof["success"], prof["errors"]
    assert prof["data"]["constructs"]

    # Profile is retrievable
    got = client.get(f"/api/v1/students/{sid}/profile").json()
    assert got["success"]

    # Recommendations (generated + ranked)
    recs = client.post(f"/api/v1/students/{sid}/recommendations", json={}).json()
    assert recs["success"], recs["errors"]
    assert recs["data"]["recommendations"]
    top = recs["data"]["recommendations"][0]

    # Explanation references the career and is non-empty
    expl = client.get(f"/api/v1/recommendations/{top['recommendation_id']}/explanation").json()
    assert expl["success"]
    assert expl["data"]["content"].strip()

    # AI coach responds
    chat = client.post("/api/v1/conversations",
                       json={"message": "Tell me about data scientist", "student_id": sid}).json()
    assert chat["success"]
    assert chat["data"]["response"].strip()


def test_missing_profile_returns_404():
    client = _client()
    resp = client.get("/api/v1/students/nobody/profile")
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "NOT_FOUND"
