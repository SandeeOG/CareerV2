"""Application DTOs and the service-result envelope (401 §12, 403 §10).

Application services return a transport-independent `ServiceResult`; the API
layer maps it to the HTTP response envelope. DTOs are kept separate from domain
entities (401 §25 DO) so transport concerns never leak into the domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class ErrorCode(str, Enum):
    """Standardized error codes (401 §18)."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class ServiceError:
    code: ErrorCode
    message: str


@dataclass(frozen=True, slots=True)
class ServiceResult(Generic[T]):
    """Standardized application result (401 §12)."""

    success: bool
    data: T | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[ServiceError, ...] = field(default_factory=tuple)
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: T, *, warnings: tuple[str, ...] = (), **metadata: str
           ) -> "ServiceResult[T]":
        return cls(True, data=data, warnings=warnings, metadata=metadata)

    @classmethod
    def fail(cls, code: ErrorCode, message: str) -> "ServiceResult[T]":
        return cls(False, errors=(ServiceError(code, message),))


# -- read-friendly DTOs ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvidenceSummaryDTO:
    student_id: str
    evidence_count: int
    conflicts: int
    completion: float | None


@dataclass(frozen=True, slots=True)
class ProfileDTO:
    profile_id: str
    student_id: str
    version: int
    constructs: tuple[tuple[str, float], ...]
    domains: tuple[tuple[str, float], ...]
    completeness: float | None


@dataclass(frozen=True, slots=True)
class RecommendationDTO:
    recommendation_id: str
    career_id: str
    overall_score: float
    confidence: float
    skill_gap_count: int


@dataclass(frozen=True, slots=True)
class RecommendationListDTO:
    student_id: str
    recommendations: tuple[RecommendationDTO, ...]


@dataclass(frozen=True, slots=True)
class ExplanationDTO:
    explanation_id: str
    recommendation_id: str
    content: str
    provider: str
    confidence: float | None


@dataclass(frozen=True, slots=True)
class AgentReplyDTO:
    intent: str
    response: str
    needs_clarification: bool
    actions: tuple[str, ...]
