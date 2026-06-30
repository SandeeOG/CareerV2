"""Explanation Engine (26_EXPLANATION_ENGINE.md).

Separates reasoning from communication. It builds a deterministic Decision Graph
and Explanation Object from a recommendation, then (optionally) lets a
provider-agnostic LLM translate it into natural language. The LLM never invents
scores, evidence, skills, careers or confidence (INV-05, §19); every statement
traces to the Explanation Object. The deterministic core never modifies the
recommendation (INV-04).
"""

from __future__ import annotations

from dataclasses import dataclass

from ...contracts import (
    BaseEngine,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    IntelligenceLayer,
)
from ...domain.common.confidence import Confidence
from ...domain.common.events import DomainEvent, EventName
from ...domain.common.identifiers import ExplanationId
from ...domain.common.versioning import Version
from ...domain.explanation.explanation import Explanation
from ...domain.recommendation.evidence import EvidenceCategory, RecommendationEvidence
from ...domain.recommendation.recommendation import Recommendation
from .decision_graph import (
    DecisionEdge,
    DecisionEdgeType,
    DecisionGraph,
    DecisionNode,
    DecisionNodeType,
)
from .explanation_object import (
    ExplanationObject,
    Improvement,
    LLMPort,
    PromptPackage,
    PromptSection,
    UncertaintyKind,
    UncertaintySource,
)

ENGINE_VERSION = Version(1, "P2")
_PROMPT_TEMPLATE_VERSION = "explanation-prompt-v1"
_LOW_SCORE = 50.0
_LOW_CONFIDENCE = 0.5


@dataclass(frozen=True, slots=True)
class ExplanationInput:
    recommendation: Recommendation
    career_name: str = ""
    question: str = "Why was this career recommended?"


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    explanation_object: ExplanationObject
    prompt_package: PromptPackage
    explanation: Explanation


class ExplanationEngine(BaseEngine[ExplanationInput, ExplanationResult]):
    """Deterministic reasoning + optional language generation (26 §1)."""

    def __init__(self, llm: LLMPort | None = None) -> None:
        self._llm = llm

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="explanation_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.EXPLANATION,
            description="Builds Decision Graphs and explanations from recommendations.",
            deterministic=self._llm is None,
        )

    def _run(
        self, request: EngineRequest[ExplanationInput]
    ) -> EngineOutcome[ExplanationResult]:
        rec = request.payload.recommendation
        career_name = request.payload.career_name or rec.career_id.value

        graph = self._decision_graph(rec, career_name)
        contradictory = self._contradictory(rec)
        uncertainty = self._uncertainty(rec)
        improvements = self._improvements(rec)
        summary = self._summary(rec, career_name)
        narrative = self._confidence_narrative(rec)

        obj = ExplanationObject(
            id=ExplanationId(f"explanation_{rec.id.value}"),
            recommendation_id=rec.id,
            decision_graph=graph,
            confidence=rec.confidence,
            supporting_evidence=rec.evidence,
            contradictory_evidence=contradictory,
            uncertainty=uncertainty,
            skill_gaps=rec.skill_gaps,
            education_gaps=rec.education_gaps,
            suggested_improvements=improvements,
            alternative_careers=rec.alternative_careers,
            summary=summary,
            confidence_narrative=narrative,
        )

        prompt = self._prompt_package(obj, career_name, request.payload.question)

        warnings: list[str] = []
        content, provider = self._render(prompt, obj, career_name)
        if self._llm is not None and not self._is_faithful(content, career_name):
            warnings.append(
                "LLM output failed faithfulness validation; used deterministic "
                "explanation instead (26 INV-08)."
            )
            content = self._deterministic_text(obj, career_name)
            provider = "deterministic_template"

        explanation = Explanation(
            id=obj.id,
            recommendation_id=rec.id,
            content=content,
            explanation_version=ENGINE_VERSION,
            provider=provider,
            confidence=rec.confidence,
        )
        result = ExplanationResult(obj, prompt, explanation)
        return EngineOutcome(
            result=result,
            confidence=rec.confidence,
            events=[DomainEvent(EventName.EXPLANATION_GENERATED, rec.id.value,
                                correlation_id=request.context.correlation_id)],
            warnings=warnings,
            metrics={
                "decision_nodes": str(len(graph.nodes)),
                "decision_edges": str(len(graph.edges)),
                "improvements": str(len(improvements)),
            },
        )

    # -- decision graph ----------------------------------------------------

    def _decision_graph(self, rec: Recommendation, career_name: str) -> DecisionGraph:
        nodes: list[DecisionNode] = [
            DecisionNode("rec", DecisionNodeType.RECOMMENDATION,
                         f"Recommendation ({rec.overall_score.value:.0f})", rec.id.value),
            DecisionNode("career", DecisionNodeType.CAREER, career_name, rec.career_id.value),
        ]
        edges: list[DecisionEdge] = [
            DecisionEdge("rec", "career", DecisionEdgeType.ALIGNED_WITH)
        ]
        for ds in rec.dimension_scores:
            dim_id = f"dim:{ds.dimension.value}"
            nodes.append(
                DecisionNode(dim_id, DecisionNodeType.DIMENSION,
                             f"{ds.dimension.value} ({ds.score.value:.0f})",
                             ds.dimension.value)
            )
            edge_type = (
                DecisionEdgeType.STRENGTHENS
                if ds.score.value >= _LOW_SCORE
                else DecisionEdgeType.WEAKENS
            )
            edges.append(DecisionEdge(dim_id, "rec", edge_type))
            for i, ev_id in enumerate(ds.evidence):
                ev_node = f"ev:{ds.dimension.value}:{i}"
                nodes.append(
                    DecisionNode(ev_node, DecisionNodeType.EVIDENCE, ev_id.value, ev_id.value)
                )
                edges.append(DecisionEdge(dim_id, ev_node, DecisionEdgeType.SUPPORTED_BY))
        for gap in rec.skill_gaps:
            skill_node = f"skill:{gap.skill_id.value}"
            nodes.append(
                DecisionNode(skill_node, DecisionNodeType.SKILL, gap.skill_id.value,
                             gap.skill_id.value)
            )
            edges.append(DecisionEdge("career", skill_node, DecisionEdgeType.REQUIRES))
            edges.append(
                DecisionEdge("rec", skill_node, DecisionEdgeType.MISSING,
                             note=f"{gap.gap_levels} level(s) short")
            )
        return DecisionGraph(tuple(nodes), tuple(edges))

    # -- analysis ----------------------------------------------------------

    @staticmethod
    def _contradictory(rec: Recommendation) -> tuple[RecommendationEvidence, ...]:
        """Expose evidence against the recommendation (26 §13)."""
        out = []
        for ds in rec.dimension_scores:
            if ds.score.value < _LOW_SCORE:
                out.append(
                    RecommendationEvidence(
                        category=EvidenceCategory.BEHAVIOURAL_ALIGNMENT,
                        summary=f"Lower {ds.dimension.value} alignment "
                                f"({ds.score.value:.0f}/100).",
                        dimension=ds.dimension,
                    )
                )
        return tuple(out)

    @staticmethod
    def _uncertainty(rec: Recommendation) -> tuple[UncertaintySource, ...]:
        out: list[UncertaintySource] = []
        if rec.confidence.value.value < _LOW_CONFIDENCE:
            out.append(
                UncertaintySource(UncertaintyKind.SPARSE_PROFILE,
                                  "Overall confidence is low; profile may be sparse.")
            )
        for ds in rec.dimension_scores:
            if ds.confidence is not None and ds.confidence.value.value < _LOW_CONFIDENCE:
                out.append(
                    UncertaintySource(
                        UncertaintyKind.LIMITED_OBSERVATIONS,
                        f"Limited data for the {ds.dimension.value} dimension.",
                    )
                )
        if rec.skill_gaps:
            out.append(
                UncertaintySource(UncertaintyKind.MISSING_EVIDENCE,
                                  f"{len(rec.skill_gaps)} skill gap(s) reduce certainty.")
            )
        return tuple(out)

    @staticmethod
    def _improvements(rec: Recommendation) -> tuple[Improvement, ...]:
        out = []
        for gap in rec.skill_gaps:
            out.append(
                Improvement(
                    title=f"Develop '{gap.skill_id.value}' from level "
                          f"{gap.current_proficiency.value} to "
                          f"{gap.required_proficiency.value}",
                    steps=("Take a structured course", "Complete a practical project",
                           "Add the work to your portfolio"),
                    target=gap.skill_id.value,
                )
            )
        return tuple(out)

    @staticmethod
    def _summary(rec: Recommendation, career_name: str) -> str:
        strength = "a strong" if rec.overall_score.value >= 70 else (
            "a moderate" if rec.overall_score.value >= 50 else "a possible"
        )
        return (
            f"{career_name} appears to be {strength} match "
            f"(score {rec.overall_score.value:.0f}/100)."
        )

    @staticmethod
    def _confidence_narrative(rec: Recommendation) -> str:
        c = rec.confidence.value.value
        if c >= 0.7:
            return "High confidence: multiple consistent evidence sources support this."
        if c >= 0.5:
            return "Moderate confidence: supported by available evidence with some gaps."
        return "Low confidence: limited evidence; treat this as exploratory."

    # -- prompt + rendering ------------------------------------------------

    def _prompt_package(
        self, obj: ExplanationObject, career_name: str, question: str
    ) -> PromptPackage:
        sections = [
            PromptSection("Summary", obj.summary),
            PromptSection("Confidence", obj.confidence_narrative),
            PromptSection(
                "Supporting evidence",
                "\n".join(f"- {e.summary}" for e in obj.supporting_evidence) or "- (none)",
            ),
        ]
        if obj.contradictory_evidence:
            sections.append(
                PromptSection(
                    "Counter-evidence",
                    "\n".join(f"- {e.summary}" for e in obj.contradictory_evidence),
                )
            )
        if obj.uncertainty:
            sections.append(
                PromptSection(
                    "Uncertainty",
                    "\n".join(f"- {u.detail}" for u in obj.uncertainty),
                )
            )
        if obj.suggested_improvements:
            sections.append(
                PromptSection(
                    "Suggested improvements",
                    "\n".join(f"- {i.title}" for i in obj.suggested_improvements),
                )
            )
        system = (
            "You are Detective Monkey, an expert AI Career Mentor — part educational "
            "advisor, labour-market analyst, learning coach and decision-support "
            "system. Explain the recommendation using ONLY the structured facts "
            "provided; never invent scores, evidence, skills, careers or confidence. "
            "Don't merely answer — guide: explain why, surface trade-offs, recommend "
            "a concrete next step, and encourage the student. Be warm and specific, "
            "and communicate uncertainty honestly."
        )
        formatting = "Plain, encouraging language. Mention the career by name. 2-4 short paragraphs."
        return PromptPackage(
            system_prompt=system,
            sections=tuple(sections),
            user_question=question,
            formatting_rules=formatting,
            template_version=_PROMPT_TEMPLATE_VERSION,
        )

    def _render(
        self, prompt: PromptPackage, obj: ExplanationObject, career_name: str
    ) -> tuple[str, str]:
        if self._llm is not None:
            return self._llm.generate(prompt), "llm"
        return self._deterministic_text(obj, career_name), "deterministic_template"

    @staticmethod
    def _deterministic_text(obj: ExplanationObject, career_name: str) -> str:
        lines = [obj.summary, "", obj.confidence_narrative, ""]
        if obj.supporting_evidence:
            lines.append("Why it fits:")
            lines.extend(f"- {e.summary}" for e in obj.supporting_evidence)
            lines.append("")
        if obj.contradictory_evidence:
            lines.append("Worth weighing:")
            lines.extend(f"- {e.summary}" for e in obj.contradictory_evidence)
            lines.append("")
        if obj.suggested_improvements:
            lines.append("To strengthen this path:")
            lines.extend(f"- {i.title}" for i in obj.suggested_improvements)
        return "\n".join(lines).strip()

    @staticmethod
    def _is_faithful(content: str, career_name: str) -> bool:
        """Basic faithfulness check (26 §19): non-empty and references the career."""
        return bool(content.strip()) and career_name.lower() in content.lower()
