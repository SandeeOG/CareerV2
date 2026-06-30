"""Engine contracts (20_ENGINE_CONTRACTS.md / 18_CORE_INTELLIGENCE_ARCHITECTURE.md).

The uniform contract every engine implements, plus the shared execution context
and registry. Engine *implementations* live in ``detective_monkey.engines``.
"""

from .context import IntelligenceContext
from .engine import (
    CONTRACT_VERSION,
    RETRYABLE_ERRORS,
    BaseEngine,
    EngineError,
    EngineErrorType,
    EngineException,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    EngineResponse,
    EngineStatus,
    HealthReport,
    HealthState,
    IntelligenceLayer,
)
from .registry import EngineRegistry

__all__ = [
    "IntelligenceContext",
    "BaseEngine",
    "EngineRequest",
    "EngineResponse",
    "EngineOutcome",
    "EngineStatus",
    "EngineError",
    "EngineErrorType",
    "EngineException",
    "EngineMetadata",
    "HealthReport",
    "HealthState",
    "IntelligenceLayer",
    "EngineRegistry",
    "CONTRACT_VERSION",
    "RETRYABLE_ERRORS",
]
