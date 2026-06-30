"""Student — the core identity entity (11_STUDENT_INTELLIGENCE_MODEL.md §4).

The Student entity intentionally holds *only* stable identity information and
"very little intelligence" (11 §4). All processed intelligence lives in the
Student Intelligence Profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..common.identifiers import StudentId


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StudentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Student:
    """Stable identity for an individual using the platform."""

    id: StudentId
    account_id: str = ""
    status: StudentStatus = StudentStatus.ACTIVE
    created_at: datetime = field(default_factory=_utcnow)
