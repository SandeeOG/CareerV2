"""Career Intelligence Agent (28_CAREER_INTELLIGENCE_AGENT.md).

The conversational orchestration layer: "Think with the platform. Speak with the
LLM" (§2). It detects intent, plans the conversation deterministically, retrieves
context, orchestrates platform engines through their contracts, and assembles a
grounded response. It never computes recommendations (INV-01), never invents
reasoning (INV-02/03), and prefers clarification over speculation (§10).
"""

from __future__ import annotations

from ...contracts import (
    BaseEngine,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    EngineStatus,
    IntelligenceLayer,
)
from ...domain.common.versioning import Version
from ..explanation.engine import ExplanationInput
from ..retrieval.intent import Intent, classify
from ..retrieval.packages import ContextPackage
from .types import (
    AgentDependencies,
    AgentInput,
    CareerAgentResponse,
    ConversationPlan,
)

ENGINE_VERSION = Version(1, "P2")

# Intent -> capability name (28 §6, §7 capability registry).
_CAPABILITY = {
    Intent.EXPLANATION: "explain_recommendation",
    Intent.RECOMMENDATION: "recommend",
    Intent.SKILL_GAP: "explain_recommendation",
    Intent.CAREER_EXPLORATION: "retrieve_and_answer",
    Intent.LEARNING_PLAN: "retrieve_and_answer",
    Intent.UNIVERSITY: "retrieve_and_answer",
    Intent.SCHOLARSHIP: "retrieve_and_answer",
    Intent.PLANNING: "retrieve_and_answer",
    Intent.CONVERSATION: "retrieve_and_answer",
}


class CareerIntelligenceAgent(BaseEngine[AgentInput, CareerAgentResponse]):
    """Deterministic orchestrator over platform engines (28 §1)."""

    def __init__(self, deps: AgentDependencies | None = None) -> None:
        self._deps = deps or AgentDependencies()

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="career_intelligence_agent",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.INTERACTION,
            description="Conversational orchestrator over platform intelligence.",
            deterministic=self._deps.llm is None,
        )

    def _run(self, request: EngineRequest[AgentInput]) -> EngineOutcome[CareerAgentResponse]:
        payload = request.payload
        intent = payload.intent_override or classify(payload.message)
        capability = _CAPABILITY.get(intent, "retrieve_and_answer")

        if capability == "explain_recommendation":
            return self._explain(request, intent)
        if capability == "recommend":
            return self._recommend(request, intent)
        return self._retrieve_and_answer(request, intent)

    # -- capabilities ------------------------------------------------------

    def _explain(self, request, intent: Intent) -> EngineOutcome[CareerAgentResponse]:
        payload = request.payload
        required = ("recommendation", "explanation_engine")
        missing = self._missing(
            recommendation=payload.recommendation is not None,
            explanation_engine=self._deps.explanation_engine is not None,
        )
        if missing:
            return self._clarify(intent, "explain_recommendation", required, missing,
                                 "I need a generated recommendation before I can explain it. "
                                 "Would you like me to generate recommendations first?")
        result = self._deps.explanation_engine.execute(  # type: ignore[union-attr]
            EngineRequest(request.context,
                          ExplanationInput(payload.recommendation, payload.career_name))
        )
        text = (
            result.result.explanation.content
            if result.ok and result.result is not None
            else "I could not produce an explanation right now."
        )
        plan = ConversationPlan(intent, "explain_recommendation", required,
                                platform_actions=("explanation_engine",),
                                response_strategy="explain")
        return self._respond(intent, plan, text, ("explanation_engine",))

    def _recommend(self, request, intent: Intent) -> EngineOutcome[CareerAgentResponse]:
        payload = request.payload
        required = ("recommendation_request", "recommendation_engine")
        missing = self._missing(
            recommendation_request=payload.recommendation_request is not None,
            recommendation_engine=self._deps.recommendation_engine is not None,
        )
        if missing:
            return self._clarify(intent, "recommend", required, missing,
                                 "To recommend careers I need your intelligence profile and "
                                 "candidate careers. Shall we complete an assessment first?")
        rec_resp = self._deps.recommendation_engine.execute(  # type: ignore[union-attr]
            EngineRequest(request.context, payload.recommendation_request)
        )
        actions = ["recommendation_engine"]
        recommendations = (
            rec_resp.result.recommendations if rec_resp.ok and rec_resp.result else ()
        )
        if not recommendations:
            return self._respond(intent,
                                  ConversationPlan(intent, "recommend", required,
                                                   platform_actions=tuple(actions)),
                                  "I couldn't find a suitable career match yet.",
                                  tuple(actions))
        top = recommendations[0]
        text = (
            f"Your strongest match is {top.career_id.value} "
            f"(score {top.overall_score.value:.0f}/100)."
        )
        if self._deps.explanation_engine is not None:
            actions.append("explanation_engine")
            expl = self._deps.explanation_engine.execute(
                EngineRequest(request.context,
                              ExplanationInput(top, payload.career_name or top.career_id.value))
            )
            if expl.ok and expl.result is not None:
                text = expl.result.explanation.content
        plan = ConversationPlan(intent, "recommend", required,
                                platform_actions=tuple(actions),
                                response_strategy="recommend_then_explain")
        return self._respond(intent, plan, text, tuple(actions))

    def _retrieve_and_answer(self, request, intent: Intent) -> EngineOutcome[CareerAgentResponse]:
        payload = request.payload
        required = ("retrieval_input", "retrieval_engine")
        if payload.retrieval_input is None or self._deps.retrieval_engine is None:
            return self._clarify(
                intent, "retrieve_and_answer", required,
                self._missing(retrieval_input=payload.retrieval_input is not None,
                              retrieval_engine=self._deps.retrieval_engine is not None),
                "Could you tell me a bit more about what you'd like to explore?")
        ctx_resp = self._deps.retrieval_engine.execute(
            EngineRequest(request.context, payload.retrieval_input)
        )
        context: ContextPackage | None = ctx_resp.result if ctx_resp.ok else None
        text = self._answer_from_context(payload.message, context)
        plan = ConversationPlan(intent, "retrieve_and_answer", required,
                                platform_actions=("knowledge_retrieval_engine",),
                                response_strategy="retrieve_then_answer")
        return self._respond(intent, plan, text, ("knowledge_retrieval_engine",),
                             context=context)

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _missing(**checks: bool) -> tuple[str, ...]:
        return tuple(name for name, present in checks.items() if not present)

    def _clarify(self, intent, capability, required, missing, question
                 ) -> EngineOutcome[CareerAgentResponse]:
        plan = ConversationPlan(intent, capability, required, missing_info=missing,
                                response_strategy="clarify")
        response = CareerAgentResponse(
            intent=intent, plan=plan, response=question,
            platform_actions=(), needs_clarification=True,
        )
        return EngineOutcome(
            result=response,
            status=EngineStatus.PARTIAL,
            warnings=[f"Clarification required; missing: {', '.join(missing)}."],
            metrics={"intent": intent.value, "capability": capability,
                     "clarification": "true"},
        )

    def _respond(self, intent, plan, text, actions, context=None
                 ) -> EngineOutcome[CareerAgentResponse]:
        # Response validation (28 §17): never return empty.
        warnings: list[str] = []
        if not text.strip():
            text = "I don't have enough information to answer that yet."
            warnings.append("Empty response replaced by a safe fallback (28 §17).")
        response = CareerAgentResponse(
            intent=intent, plan=plan, response=text,
            platform_actions=actions, retrieved_context=context,
        )
        return EngineOutcome(
            result=response,
            warnings=warnings,
            metrics={"intent": intent.value, "capability": plan.capability,
                     "actions": ",".join(actions)},
        )

    @staticmethod
    def _answer_from_context(message: str, context: ContextPackage | None) -> str:
        if context is None or not context.items:
            return ("I couldn't find relevant information yet. Could you share more "
                    "detail about your interests or goals?")
        top = context.items[:3]
        lines = ["Here's what I found relevant:"]
        lines.extend(f"- {i.label}: {i.content}" for i in top)
        return "\n".join(lines)
