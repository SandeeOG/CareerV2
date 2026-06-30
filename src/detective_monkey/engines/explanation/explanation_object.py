"""The Explanation Object and prompt package (26_EXPLANATION_ENGINE.md §9, §17, §18).

The Explanation Object is the deterministic artifact the engine produces (§9). An
LLM, if present, translates it into natural language but may never invent scores,
evidence, skills, careers or confidence (§19).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from ...domain.common.confidence import Confidence
from ...domain.common.identifiers import ExplanationId, RecommendationId
from ...domain.recommendation.evidence import RecommendationEvidence
from ...domain.recommendation.recommendation import AlternativeCareer
from ...domain.skills.skill_gap import SkillGap
from ...domain.education.student_education import EducationGap
from .decision_graph import DecisionGraph


class ExplanationLevel(str, Enum):
    """Supported explanation detail levels (26 §17)."""

    SUMMARY = "summary"
    EVIDENCE = "evidence"
    DETAILED = "detailed"
    FULL_GRAPH = "full_graph"


class UncertaintyKind(str, Enum):
    """Explicit uncertainty sources (26 §12)."""

    MISSING_EVIDENCE = "missing_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    OUTDATED_EVIDENCE = "outdated_evidence"
    LIMITED_OBSERVATIONS = "limited_observations"
    SPARSE_PROFILE = "sparse_profile"


@dataclass(frozen=True, slots=True)
class UncertaintySource:
    kind: UncertaintyKind
    detail: str


@dataclass(frozen=True, slots=True)
class Improvement:
    """An actionable improvement step (26 §15)."""

    title: str
    steps: tuple[str, ...] = field(default_factory=tuple)
    target: str = ""


@dataclass(frozen=True, slots=True)
class ExplanationObject:
    """Deterministic explanation artifact (26 §9)."""

    id: ExplanationId
    recommendation_id: RecommendationId
    decision_graph: DecisionGraph
    confidence: Confidence
    supporting_evidence: tuple[RecommendationEvidence, ...] = field(default_factory=tuple)
    contradictory_evidence: tuple[RecommendationEvidence, ...] = field(default_factory=tuple)
    uncertainty: tuple[UncertaintySource, ...] = field(default_factory=tuple)
    skill_gaps: tuple[SkillGap, ...] = field(default_factory=tuple)
    education_gaps: tuple[EducationGap, ...] = field(default_factory=tuple)
    suggested_improvements: tuple[Improvement, ...] = field(default_factory=tuple)
    alternative_careers: tuple[AlternativeCareer, ...] = field(default_factory=tuple)
    summary: str = ""
    confidence_narrative: str = ""


@dataclass(frozen=True, slots=True)
class PromptSection:
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class PromptPackage:
    """Deterministically-assembled LLM input (26 §18). Versioned (§18)."""

    system_prompt: str
    sections: tuple[PromptSection, ...]
    user_question: str
    formatting_rules: str
    template_version: str


@runtime_checkable
class LLMPort(Protocol):
    """Provider-agnostic language generation port (00 §11, 26 §18).

    Implementations live outside the domain/engines (Phase 3). The Explanation
    Engine works without one, producing deterministic text.
    """

    def generate(self, prompt: PromptPackage) -> str: ...
