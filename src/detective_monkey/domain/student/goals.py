"""Student goals and preferences (11_STUDENT_INTELLIGENCE_MODEL.md §7 "Explicit
User Input", §12 "Aspirational"; consumed by 25_RECOMMENDATION_ENGINE.md §11
Goal Match).

Goals are explicit user input — aspirations, not measured intelligence — so they
live alongside the student domain but outside the SIP (the SIP holds processed
intelligence only, 11 §9). Goals influence recommendations without dominating
them (25 §11).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.identifiers import StudentId


@dataclass(frozen=True, slots=True)
class StudentGoals:
    """Explicitly declared student aspirations and preferences."""

    student_id: StudentId
    dream_careers: tuple[str, ...] = field(default_factory=tuple)
    preferred_countries: tuple[str, ...] = field(default_factory=tuple)
    preferred_industries: tuple[str, ...] = field(default_factory=tuple)
    work_preferences: tuple[str, ...] = field(default_factory=tuple)
    salary_expectation: float | None = None
