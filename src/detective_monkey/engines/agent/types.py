"""Career Agent request/response and plan types (28_CAREER_INTELLIGENCE_AGENT.md §9, §20).

The agent is an orchestrator, not a source of intelligence (§1). It produces a
deterministic conversation plan, records which platform engines it invoked, and
returns a response grounded in retrieved/explained context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.recommendation.contracts import RecommendationRequest
from ...domain.recommendation.recommendation import Recommendation
from ..explanation.explanation_object import LLMPort
from ..retrieval.engine import RetrievalInput
from ..retrieval.intent import Intent
from ..retrieval.packages import ContextPackage


@dataclass(frozen=True, slots=True)
class AgentInput:
    """A user turn plus the canonical artifacts the agent may orchestrate over."""

    message: str
    intent_override: Intent | None = None
    career_name: str = ""
    retrieval_input: RetrievalInput | None = None
    recommendation: Recommendation | None = None
    recommendation_request: RecommendationRequest | None = None


@dataclass(frozen=True, slots=True)
class ConversationPlan:
    """A deterministic plan built before any language generation (28 §9)."""

    intent: Intent
    capability: str
    required_info: tuple[str, ...] = field(default_factory=tuple)
    missing_info: tuple[str, ...] = field(default_factory=tuple)
    platform_actions: tuple[str, ...] = field(default_factory=tuple)
    response_strategy: str = ""


@dataclass(frozen=True, slots=True)
class CareerAgentResponse:
    """The agent output (28 §20)."""

    intent: Intent
    plan: ConversationPlan
    response: str
    platform_actions: tuple[str, ...] = field(default_factory=tuple)
    retrieved_context: ContextPackage | None = None
    needs_clarification: bool = False


@dataclass(frozen=True, slots=True)
class AgentDependencies:
    """Injected platform engines the agent orchestrates through contracts (28 §11).

    All optional so the agent degrades gracefully when a capability's engine is
    not wired. The agent never embeds business logic itself.
    """

    retrieval_engine: object | None = None
    explanation_engine: object | None = None
    recommendation_engine: object | None = None
    llm: LLMPort | None = None
