"""Assessment definitions — data, never code (21_ASSESSMENT_ENGINE.md §6, §7).

Assessment definitions and question banks are versioned data. Question text never
appears inside engine logic (INV-01); the engine reads these structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ...domain.common.versioning import Version


class QuestionType(str, Enum):
    """Supported question types (21 §8). New types should be pluggable."""

    LIKERT = "likert"
    MULTIPLE_CHOICE = "multiple_choice"
    RANKING = "ranking"
    MATRIX = "matrix"
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    SCENARIO = "scenario"
    SITUATIONAL_JUDGEMENT = "situational_judgement"
    FORCED_CHOICE = "forced_choice"
    OPEN_RESPONSE = "open_response"


class MissingPolicy(str, Enum):
    """How missing responses are handled (21 §12). Configurable."""

    REJECT = "reject"
    SKIP = "skip"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class Question:
    """A reusable assessment question (21 §7).

    ``construct`` names the latent characteristic the question measures (21 §16);
    questions never measure careers. ``scale_min``/``scale_max`` bound numeric and
    Likert responses and drive reverse scoring.
    """

    id: str
    construct: str
    qtype: QuestionType = QuestionType.LIKERT
    reverse_scored: bool = False
    weight: float = 1.0
    scale_min: float = 1.0
    scale_max: float = 5.0
    # Display text for the UI only. Engine logic never reads it (INV-01); it is
    # presentation metadata so questions remain free of business logic.
    prompt: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Question.id must be non-empty")
        if not self.construct.strip():
            raise ValueError("Question.construct must be non-empty")
        if self.scale_max <= self.scale_min:
            raise ValueError("Question.scale_max must exceed scale_min")
        if self.weight <= 0:
            raise ValueError("Question.weight must be positive")


@dataclass(frozen=True, slots=True)
class Section:
    """An independent section of an assessment (21 §9)."""

    id: str
    title: str
    questions: tuple[Question, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AssessmentDefinition:
    """A versioned, immutable assessment definition (21 §6, INV-02)."""

    id: str
    version: Version
    sections: tuple[Section, ...] = field(default_factory=tuple)
    missing_policy: MissingPolicy = MissingPolicy.INCOMPLETE

    def questions(self) -> tuple[Question, ...]:
        return tuple(q for s in self.sections for q in s.questions)

    def question_ids(self) -> set[str]:
        return {q.id for q in self.questions()}
