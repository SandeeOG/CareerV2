"""The mandatory engine contract (20_ENGINE_CONTRACTS.md).

Every processing component in Detective Monkey — deterministic or AI — implements
this single contract: one `EngineRequest` in, one `EngineResponse` out, through a
fixed lifecycle (§3, §30). No stage may be skipped and successful execution never
relies on exceptions (§7). Errors are structured (§11); engines emit events (§13),
record metrics (§14), expose health (§20) and metadata (§5), and are versioned
independently of their contract (§16).

Engines own no UI and no persistence (§2); allowed side effects are limited to
events, metrics and logging (§19).
"""

from __future__ import annotations

import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

from ..domain.common.attributes import Attributes
from ..domain.common.confidence import Confidence
from ..domain.common.events import DomainEvent
from ..domain.common.provenance import Provenance
from ..domain.common.versioning import Version
from .context import IntelligenceContext

PayloadT = TypeVar("PayloadT")
ResultT = TypeVar("ResultT")

# The contract version shared by all engines (20 §16). Engine *implementation*
# versions evolve independently of this.
CONTRACT_VERSION = Version(1, "P2")


class IntelligenceLayer(str, Enum):
    """The six layers of the Core Intelligence Architecture (18 §3).

    The deterministic boundary (18 §16) falls after DECISION.
    """

    EVIDENCE = "evidence"
    KNOWLEDGE = "knowledge"
    INFERENCE = "inference"
    DECISION = "decision"
    EXPLANATION = "explanation"
    INTERACTION = "interaction"

    @property
    def is_deterministic(self) -> bool:
        return self in {
            IntelligenceLayer.EVIDENCE,
            IntelligenceLayer.KNOWLEDGE,
            IntelligenceLayer.INFERENCE,
            IntelligenceLayer.DECISION,
        }


class EngineStatus(str, Enum):
    """Outcome status of an execution (20 §7)."""

    SUCCESS = "success"
    PARTIAL = "partial"  # graceful degradation (18 §15, 23 §21)
    FAILED = "failed"


class EngineErrorType(str, Enum):
    """Structured error categories (20 §11). No generic exceptions."""

    VALIDATION = "validation"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INTERNAL = "internal"


# Errors that orchestration may retry (20 §12). Retry lives outside the engine.
RETRYABLE_ERRORS = frozenset(
    {EngineErrorType.TIMEOUT, EngineErrorType.UNAVAILABLE, EngineErrorType.DEPENDENCY}
)


@dataclass(frozen=True, slots=True)
class EngineError:
    """A structured error (20 §11)."""

    error_type: EngineErrorType
    code: str
    message: str

    @property
    def retryable(self) -> bool:
        return self.error_type in RETRYABLE_ERRORS


class EngineException(Exception):
    """Raised inside `_run` to signal a structured failure.

    `BaseEngine.execute` converts it into a failed `EngineResponse` rather than
    letting it propagate, honouring "no generic exceptions for success" (§7/§11).
    """

    def __init__(self, error: EngineError) -> None:
        super().__init__(error.message)
        self.error = error


class HealthState(str, Enum):
    """Engine health states (20 §20)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class HealthReport:
    state: HealthState
    detail: str = ""


@dataclass(frozen=True, slots=True)
class EngineMetadata:
    """Published metadata for an engine (20 §5)."""

    engine_name: str
    engine_version: Version
    layer: IntelligenceLayer
    description: str = ""
    contract_version: Version = CONTRACT_VERSION
    deterministic: bool = True


@dataclass(frozen=True, slots=True)
class EngineRequest(Generic[PayloadT]):
    """The single request object every engine accepts (20 §6).

    Raw primitives are never passed between engines; everything travels inside
    the typed `payload` plus shared `context`/`configuration`/`metadata`.
    """

    context: IntelligenceContext
    payload: PayloadT
    configuration: Attributes = field(default_factory=Attributes)
    metadata: Attributes = field(default_factory=Attributes)


@dataclass(frozen=True, slots=True)
class EngineResponse(Generic[ResultT]):
    """The single response object every engine returns (20 §7)."""

    status: EngineStatus
    engine_version: Version
    result: ResultT | None = None
    confidence: Confidence | None = None
    provenance: Provenance | None = None
    events: tuple[DomainEvent, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[EngineError, ...] = field(default_factory=tuple)
    metrics: Attributes = field(default_factory=Attributes)
    metadata: Attributes = field(default_factory=Attributes)

    @property
    def ok(self) -> bool:
        return self.status in (EngineStatus.SUCCESS, EngineStatus.PARTIAL)


@dataclass(slots=True)
class EngineOutcome(Generic[ResultT]):
    """What an engine's `_run` returns; `execute` wraps it with metrics/errors.

    Using a mutable accumulator keeps engine bodies readable: append events and
    warnings as the pipeline proceeds, then return.
    """

    result: ResultT
    status: EngineStatus = EngineStatus.SUCCESS
    confidence: Confidence | None = None
    provenance: Provenance | None = None
    events: list[DomainEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, str] = field(default_factory=dict)


class BaseEngine(ABC, Generic[PayloadT, ResultT]):
    """Shared engine lifecycle (20 §3, §30).

    Subclasses implement `_run` (business logic only) and `validate` (pre-checks).
    `execute` orchestrates: validate -> run -> collect metrics -> build response,
    converting any failure into a structured `EngineResponse` (§7, §11).
    """

    @abstractmethod
    def metadata(self) -> EngineMetadata:
        """Publish engine metadata (20 §5)."""

    def health(self) -> HealthReport:
        """Default health check (20 §20). Override to verify dependencies."""
        return HealthReport(HealthState.HEALTHY)

    def validate(self, request: EngineRequest[PayloadT]) -> list[EngineError]:
        """Validate the request before execution (20 §8).

        Returns a list of structured errors; an empty list means valid. Override
        per engine. Default accepts everything.
        """
        return []

    @abstractmethod
    def _run(self, request: EngineRequest[PayloadT]) -> EngineOutcome[ResultT]:
        """Business logic only (20 §10). Pure where feasible; no persistence."""

    def execute(self, request: EngineRequest[PayloadT]) -> EngineResponse[ResultT]:
        """Run the full engine lifecycle and always return a response (never raise)."""
        version = self.metadata().engine_version
        started = time.perf_counter()

        try:
            errors = self.validate(request)
        except Exception as exc:  # validation must never crash the caller
            return self._failure(version, self._internal_error(exc), started)
        if errors:
            return EngineResponse(
                status=EngineStatus.FAILED,
                engine_version=version,
                errors=tuple(errors),
                metrics=self._metrics(started, {}),
            )

        try:
            outcome = self._run(request)
        except EngineException as exc:
            return self._failure(version, exc.error, started)
        except Exception as exc:  # defensive: structured INTERNAL error (§11)
            return self._failure(version, self._internal_error(exc), started)

        return EngineResponse(
            status=outcome.status,
            engine_version=version,
            result=outcome.result,
            confidence=outcome.confidence,
            provenance=outcome.provenance,
            events=tuple(outcome.events),
            warnings=tuple(outcome.warnings),
            metrics=self._metrics(started, outcome.metrics),
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _internal_error(exc: Exception) -> EngineError:
        return EngineError(
            EngineErrorType.INTERNAL,
            code="internal_error",
            message=f"{type(exc).__name__}: {exc}",
        )

    def _failure(
        self, version: Version, error: EngineError, started: float
    ) -> EngineResponse[ResultT]:
        return EngineResponse(
            status=EngineStatus.FAILED,
            engine_version=version,
            errors=(error,),
            metrics=self._metrics(started, {}),
        )

    @staticmethod
    def _metrics(started: float, extra: dict[str, str]) -> Attributes:
        duration_ms = (time.perf_counter() - started) * 1000.0
        items = {"execution_ms": f"{duration_ms:.3f}", **extra}
        return Attributes(tuple(items.items()))
