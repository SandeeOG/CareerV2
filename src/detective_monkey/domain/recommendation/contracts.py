"""Recommendation Engine I/O contracts (25_RECOMMENDATION_ENGINE.md §19, §20).

These are *data contracts only* — the request the engine consumes and the
response it produces. The orchestration and scoring logic (the engine itself)
belongs to Phase 2 and depends on `20_ENGINE_CONTRACTS.md`,
`23_STUDENT_INTELLIGENCE_ENGINE.md` and `24_FEATURE_ENGINEERING_ENGINE.md`,
which are not yet written. Defining the contract first follows
00_ARCHITECTURE_PRINCIPLES.md §14 (Contract First Development).

Only canonical domain objects may enter the request (16_RECOMMENDATION_MODEL.md
§4): the Student Intelligence Profile, the career graph, labour-market
snapshots and configuration. Raw assessment answers, LLM output, chat history
and UI state are forbidden inputs and are therefore not representable here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..career.career import Career
from ..common.attributes import Attributes
from ..common.events import DomainEvent
from ..education.student_education import StudentEducation
from ..labour_market.snapshot import LabourMarketSnapshot
from ..skills.student_skill import StudentSkill
from ..student.goals import StudentGoals
from ..student.profile import StudentIntelligenceProfile
from .recommendation import Recommendation
from .weights import WeightConfiguration


class WarningSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class RecommendationWarning:
    """A non-fatal diagnostic emitted during recommendation (25 §19 Output).

    Examples: low profile completeness, missing labour-market snapshot for a
    region, a dimension that could not be scored due to absent evidence.
    """

    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.LOW

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("RecommendationWarning.code must be non-empty")


@dataclass(frozen=True, slots=True)
class RecommendationRequest:
    """The input contract for the Recommendation Engine (25 §19 Input).

    ``careers`` is the (already-resolved) slice of the Career Intelligence Graph
    the engine may consider; candidate generation narrows this further. Labour
    snapshots are optional — recommendations must still be produced when market
    data is unavailable (18 §15 graceful degradation).
    """

    profile: StudentIntelligenceProfile
    careers: tuple[Career, ...]
    weights: WeightConfiguration
    labour_market: tuple[LabourMarketSnapshot, ...] = field(default_factory=tuple)
    # Canonical student-domain inputs the matchers consume (16 §4). All optional:
    # a dimension with no input data is skipped and its weight is redistributed.
    student_skills: tuple[StudentSkill, ...] = field(default_factory=tuple)
    student_education: tuple[StudentEducation, ...] = field(default_factory=tuple)
    goals: StudentGoals | None = None
    candidate_limit: int | None = None
    configuration_version: str = ""

    def __post_init__(self) -> None:
        if not self.careers:
            raise ValueError("RecommendationRequest requires at least one career")
        if self.candidate_limit is not None and self.candidate_limit <= 0:
            raise ValueError("candidate_limit must be positive when provided")


@dataclass(frozen=True, slots=True)
class RecommendationResponse:
    """The output contract for the Recommendation Engine (25 §19 Output).

    ``recommendations`` are returned already ranked (25 §14). Warnings, events
    and metadata accompany them; the explanation layer consumes this response
    but never recomputes it (16 §22).
    """

    recommendations: tuple[Recommendation, ...] = field(default_factory=tuple)
    warnings: tuple[RecommendationWarning, ...] = field(default_factory=tuple)
    events: tuple[DomainEvent, ...] = field(default_factory=tuple)
    metadata: Attributes = field(default_factory=Attributes)
