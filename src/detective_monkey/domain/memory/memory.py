"""Memory records (19_MEMORY_ARCHITECTURE.md §5–§13, §19, §20).

Memory is personal and persistent (unlike global knowledge and recomputed
intelligence). Memory augments reasoning but never creates intelligence
(MP-01..03). Records are immutable and versioned; updates create new versions
(§20). Working Memory is never persisted (INV-05) and so is deliberately *not*
modelled as a stored record here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..common.attributes import Attributes
from ..common.identifiers import MemoryId, StudentId
from ..common.provenance import Provenance
from ..common.scores import Importance
from ..common.versioning import Version


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryType(str, Enum):
    """The persistent memory systems (19 §5).

    Semantic memory is intentionally excluded as a stored type: it belongs to
    the Knowledge Graph (19 §6, INV-06). Working memory is excluded because it is
    never persisted (INV-05).
    """

    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    LONGITUDINAL = "longitudinal"


class PrivacyLevel(str, Enum):
    """Privacy metadata controlling retrieval (19 §19)."""

    PRIVATE = "private"
    SHARED = "shared"
    INSTITUTION = "institution"
    ANONYMOUS = "anonymous"
    RESEARCH = "research"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Memory:
    """An immutable memory record (19 §12).

    ``owner`` is the student the memory belongs to, except for ``PROCEDURAL``
    memory which belongs to the platform (19 §9) and therefore has no student
    owner.
    """

    id: MemoryId
    memory_type: MemoryType
    summary: str
    version: Version
    provenance: Provenance
    privacy: PrivacyLevel = PrivacyLevel.PRIVATE
    importance: Importance = Importance.MEDIUM
    owner: StudentId | None = None
    related: tuple[MemoryId, ...] = field(default_factory=tuple)
    detail: Attributes = field(default_factory=Attributes)
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("Memory.summary must be non-empty")
        # INV-04: every (non-procedural) memory has an owner.
        if self.memory_type is not MemoryType.PROCEDURAL and self.owner is None:
            raise ValueError(
                "Non-procedural Memory requires an owner (19_MEMORY_ARCHITECTURE.md "
                "§25 INV-04)"
            )
