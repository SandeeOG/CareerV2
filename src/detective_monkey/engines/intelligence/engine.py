"""The Intelligence Engine — the single reasoning component.

Exposes exactly one public method, :meth:`IntelligenceEngine.build`, which runs
the five-stage deterministic pipeline:

    1. Signal Extraction   (signals.py)
    2. Trait Inference     (reasoner.py)
    3. Evidence Collection (reasoner.py)
    4. Profile Construction(builder.py)
    5. Confidence Estimation (confidence.py)

Extension points (LLM reasoning, knowledge-graph traversal, embeddings, Bayesian
scoring, personalization) are exposed as Protocols so future implementations can
be injected without changing the contract. None are implemented now.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..assessment.responses import AssessmentResult
from ...domain.student.student import Student
from . import confidence as confidence_stage
from . import reasoner as reasoner_stage
from . import signals as signal_stage
from .builder import build_profile
from .models import (
    ConversationContext,
    ProfileMetadata,
    StudentIntelligenceProfile,
    StudentPreferences,
    StudentSignals,
)

ENGINE_VERSION = "intelligence-v1"


# -- Extension interfaces (not implemented now) ----------------------------


@runtime_checkable
class SignalExtractor(Protocol):
    """Future LLM/embedding-based signal extraction can implement this."""

    def __call__(
        self, assessment: AssessmentResult, conversation: ConversationContext | None
    ) -> StudentSignals: ...


@runtime_checkable
class TraitReasoner(Protocol):
    """Future knowledge-graph / Bayesian reasoners can implement this."""

    def __call__(
        self,
        signals: StudentSignals,
        conversation: ConversationContext | None,
        preferences: StudentPreferences | None,
    ) -> "reasoner_stage.ReasoningResult": ...


class IntelligenceEngine:
    """Deterministic interpretation engine. Inject alternative stage strategies
    (extension points) or rely on the built-in deterministic defaults."""

    def __init__(
        self,
        *,
        signal_extractor: SignalExtractor | None = None,
        trait_reasoner: TraitReasoner | None = None,
    ) -> None:
        self._extract = signal_extractor or signal_stage.extract_signals
        self._reason = trait_reasoner or reasoner_stage.infer

    def build(
        self,
        assessment: AssessmentResult,
        student: Student,
        conversation: ConversationContext | None = None,
        preferences: StudentPreferences | None = None,
    ) -> StudentIntelligenceProfile:
        # Stage 1
        signals = self._extract(assessment, conversation)
        # Stages 2 + 3
        reasoning = self._reason(signals, conversation, preferences)
        # Stage 5 (needs signals + evidence)
        score = confidence_stage.estimate_confidence(assessment, signals, reasoning.evidence)
        # Stage 4
        metadata = ProfileMetadata(
            engine_version=ENGINE_VERSION,
            signal_count=len(signals.as_pairs()),
            evidence_count=len(reasoning.evidence),
            assessment_completeness=(
                assessment.quality.completion if assessment.quality is not None else 0.0
            ),
        )
        return build_profile(reasoning, score, metadata)
