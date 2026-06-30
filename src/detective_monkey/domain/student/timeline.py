"""Student timeline (11_STUDENT_INTELLIGENCE_MODEL.md §5).

Every action contributes to an append-only timeline. Historical events are never
destroyed (11 §5). The timeline is a source of evidence, not processed
intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.attributes import Attributes
from ..common.identifiers import StudentId


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """An immutable record of something the student did."""

    student_id: StudentId
    kind: str
    occurred_at: datetime = field(default_factory=_utcnow)
    detail: Attributes = field(default_factory=Attributes)

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("TimelineEvent.kind must be non-empty")


@dataclass(frozen=True, slots=True)
class StudentTimeline:
    """An append-only sequence of timeline events for one student."""

    student_id: StudentId
    events: tuple[TimelineEvent, ...] = field(default_factory=tuple)

    def append(self, event: TimelineEvent) -> "StudentTimeline":
        """Return a new timeline with the event appended (append-only, 11 §5)."""
        if event.student_id != self.student_id:
            raise ValueError("TimelineEvent belongs to a different student")
        return StudentTimeline(self.student_id, self.events + (event,))
