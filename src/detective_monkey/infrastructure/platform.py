"""Platform services (403_SERVICE_ARCHITECTURE.md §7, 410 config, 411 observability).

Shared technical capabilities with no business logic: clock, id generation,
configuration and structured logging. Business logic never reads environment
variables directly (400 §19) — it goes through ``ConfigurationService``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


class SystemClock:
    """Real clock (403 §7). Injectable so tests can substitute a fixed clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Deterministic clock for tests/reproducibility."""

    instant: datetime

    def now(self) -> datetime:
        return self.instant


class UuidGenerator:
    """Opaque, non-semantic id generation (30 §7)."""

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class DeterministicIdGenerator:
    """Counter-based id generator for reproducible tests."""

    _counter: list[int] = field(default_factory=lambda: [0])

    def new_id(self, prefix: str) -> str:
        self._counter[0] += 1
        return f"{prefix}_{self._counter[0]:06d}"


class InMemoryConfiguration:
    """Centralized configuration (410). Layered: explicit values then defaults."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._values.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value


class EnvConfiguration:
    """Configuration sourced from process environment variables (410).

    Deployment injects configuration; application code never changes between
    environments (60 §12). This is the one adapter allowed to read ``os.environ``
    — business logic only ever goes through the ``ConfigurationService`` port.
    Explicit ``overrides`` take precedence (useful for tests).
    """

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self._overrides = dict(overrides or {})

    def get(self, key: str, default: str | None = None) -> str | None:
        if key in self._overrides:
            return self._overrides[key]
        return os.environ.get(key, default)


def get_logger(name: str) -> logging.Logger:
    """Structured logger (411 §...). Correlation ids are passed via ``extra``."""
    return logging.getLogger(f"detective_monkey.{name}")
