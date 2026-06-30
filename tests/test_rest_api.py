"""REST adapter tests (401_API_ARCHITECTURE.md).

The envelope mapping is tested purely (no framework). The FastAPI app is tested
only when FastAPI is installed (it is an optional dependency).
"""

from __future__ import annotations

import importlib.util

import pytest

from detective_monkey.application.dto import ErrorCode, ProfileDTO, ServiceResult
from detective_monkey.interfaces.rest.envelope import http_status, to_envelope


def test_envelope_success_serializes_dto():
    dto = ProfileDTO("p1", "s1", 1, (("analytical_thinking", 90.0),), (), 1.0)
    env = to_envelope(ServiceResult.ok(dto, note="x"))
    assert env["success"] is True
    assert env["data"]["constructs"] == [["analytical_thinking", 90.0]]
    assert env["metadata"] == {"note": "x"}
    assert env["errors"] == []


def test_envelope_error_maps_status():
    result = ServiceResult.fail(ErrorCode.NOT_FOUND, "missing")
    env = to_envelope(result)
    assert env["success"] is False
    assert env["errors"][0]["code"] == "NOT_FOUND"
    assert http_status(result) == 404


_HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI optional dependency not installed")
def test_fastapi_health_and_404():
    from fastapi.testclient import TestClient

    from detective_monkey.application.container import Backend
    from detective_monkey.interfaces.rest.app import create_app

    client = TestClient(create_app(Backend()))
    assert client.get("/api/v1/health").json()["data"]["status"] == "healthy"

    resp = client.get("/api/v1/students/ghost/profile")
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "NOT_FOUND"
