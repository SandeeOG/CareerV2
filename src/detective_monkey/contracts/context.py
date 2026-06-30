"""Intelligence context (18_CORE_INTELLIGENCE_ARCHITECTURE.md §21).

Every engine executes within a shared, immutable context that carries the
versions and correlation identifiers needed for reproducibility and
observability (18 §12, §21).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from ..domain.common.versioning import VersionSet


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class IntelligenceContext:
    """Shared execution context threaded through every engine."""

    student_id: str | None = None
    input_versions: VersionSet = field(default_factory=VersionSet)
    timestamp: datetime = field(default_factory=_utcnow)
    correlation_id: str = field(default_factory=lambda: uuid4().hex)
    request_id: str = field(default_factory=lambda: uuid4().hex)
    configuration_version: str = ""
