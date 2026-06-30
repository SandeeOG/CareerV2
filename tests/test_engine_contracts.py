"""Engine-contract conformance tests (20_ENGINE_CONTRACTS.md).

Verifies the uniform lifecycle behaviour every engine inherits: structured
validation errors instead of exceptions, structured internal errors, health,
metadata, and the deterministic boundary classification.
"""

from __future__ import annotations

from detective_monkey.contracts import (
    BaseEngine,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    EngineError,
    EngineErrorType,
    EngineRegistry,
    EngineStatus,
    HealthState,
    IntelligenceContext,
    IntelligenceLayer,
    CONTRACT_VERSION,
)
from detective_monkey.domain.common.versioning import Version


class _EchoEngine(BaseEngine[int, int]):
    def metadata(self) -> EngineMetadata:
        return EngineMetadata("echo", Version(1), IntelligenceLayer.DECISION)

    def validate(self, request):
        if request.payload < 0:
            return [EngineError(EngineErrorType.VALIDATION, "negative",
                                "payload must be >= 0")]
        return []

    def _run(self, request):
        return EngineOutcome(result=request.payload * 2)


class _BoomEngine(BaseEngine[int, int]):
    def metadata(self) -> EngineMetadata:
        return EngineMetadata("boom", Version(1), IntelligenceLayer.DECISION)

    def _run(self, request):
        raise RuntimeError("kaboom")


def _req(payload: int) -> EngineRequest[int]:
    return EngineRequest(IntelligenceContext(), payload)


def test_success_path_returns_response_not_exception():
    resp = _EchoEngine().execute(_req(21))
    assert resp.status is EngineStatus.SUCCESS
    assert resp.result == 42
    assert resp.engine_version == Version(1)
    assert "execution_ms" in dict(resp.metrics.items)


def test_validation_failure_is_structured():
    resp = _EchoEngine().execute(_req(-1))
    assert resp.status is EngineStatus.FAILED
    assert resp.result is None
    assert resp.errors and resp.errors[0].error_type is EngineErrorType.VALIDATION


def test_internal_exception_becomes_structured_error():
    resp = _BoomEngine().execute(_req(1))
    assert resp.status is EngineStatus.FAILED
    assert resp.errors and resp.errors[0].error_type is EngineErrorType.INTERNAL


def test_health_and_metadata_defaults():
    eng = _EchoEngine()
    assert eng.health().state is HealthState.HEALTHY
    assert eng.metadata().contract_version == CONTRACT_VERSION


def test_deterministic_boundary_classification():
    # Evidence..Decision deterministic; Explanation/Interaction not (18 §16).
    assert IntelligenceLayer.DECISION.is_deterministic
    assert IntelligenceLayer.EVIDENCE.is_deterministic
    assert not IntelligenceLayer.EXPLANATION.is_deterministic
    assert not IntelligenceLayer.INTERACTION.is_deterministic


def test_registry_rejects_duplicate_and_resolves():
    reg = EngineRegistry()
    eng = _EchoEngine()
    reg.register(eng)
    assert reg.has("echo")
    assert reg.get("echo") is eng
    try:
        reg.register(_EchoEngine())
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("duplicate registration should raise")
