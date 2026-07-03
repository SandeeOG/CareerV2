"""DecisionSupportService — profile-aware comparisons over retrieved facts.

Compare careers, countries, universities; evaluate offers, certifications or
relocation. Every comparison is built the same way: retrieve the canonical
entity and its current dynamic facts per option, lay them out criterion by
criterion, and let the LLM (when present) narrate — the facts themselves are
always retrieved, never generated. Results are Layer 3: produced per request,
cached briefly, never stored as truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.confidence import Confidence
from ...domain.knowledge_graph.node import Node
from ..cache.cache import KnowledgeCache
from ..generators.llm import LLMPort
from ..graph.traversal import GraphTraversal
from ..models.dynamic import DynamicFact, DynamicFactType
from ..normalizers.text import slugify, tokens
from ..prompts.templates import comparison_prompt
from ..sources.dynamic import DynamicKnowledgeProvider

_DEFAULT_CRITERIA = (DynamicFactType.SALARY, DynamicFactType.DEMAND,
                     DynamicFactType.AI_DISRUPTION)
_COMPARISON_TTL = 6 * 3600  # personalized output is cached briefly, never stored


@dataclass(frozen=True, slots=True)
class ComparisonCell:
    option: str
    criterion: DynamicFactType
    facts: tuple[DynamicFact, ...] = field(default_factory=tuple)

    @property
    def known(self) -> bool:
        return bool(self.facts)


@dataclass(frozen=True, slots=True)
class DecisionReport:
    options: tuple[str, ...]
    criteria: tuple[DynamicFactType, ...]
    matrix: tuple[ComparisonCell, ...]
    summary: str
    region: str = ""
    confidence: Confidence | None = None
    generated_by_llm: bool = False

    def cell(self, option: str, criterion: DynamicFactType) -> ComparisonCell | None:
        for c in self.matrix:
            if c.option == option and c.criterion is criterion:
                return c
        return None


class DecisionSupportService:
    """Structured, retrieval-grounded decision support."""

    def __init__(
        self,
        traversal: GraphTraversal,
        dynamic_provider: DynamicKnowledgeProvider | None = None,
        cache: KnowledgeCache | None = None,
        llm: LLMPort | None = None,
    ) -> None:
        self._traversal = traversal
        self._dynamic = dynamic_provider
        self._cache = cache or KnowledgeCache()
        self._llm = llm

    def compare(
        self,
        options: tuple[str, ...],
        *,
        criteria: tuple[DynamicFactType, ...] = _DEFAULT_CRITERIA,
        region: str = "",
        student_context: str = "",
    ) -> DecisionReport:
        if len(options) < 2:
            raise ValueError("a comparison needs at least two options")
        key = KnowledgeCache.key(
            "decision",
            "-".join(sorted(slugify(o) for o in options)),
            "-".join(c.value for c in criteria),
            slugify(region),
            slugify(student_context)[:64],
        )
        return self._cache.get_or_compute(
            key,
            lambda: self._compare(tuple(options), criteria, region, student_context),
            ttl_seconds=_COMPARISON_TTL,
        )

    def evaluate(
        self,
        option: str,
        *,
        criteria: tuple[DynamicFactType, ...] = _DEFAULT_CRITERIA,
        region: str = "",
        student_context: str = "",
    ) -> DecisionReport:
        """Evaluate a single option (an offer, certification, relocation, ...)."""
        matrix = self._cells((option,), criteria, region)
        nodes = self._nodes((option,))
        summary, used_llm = self._narrate(nodes, matrix, student_context)
        return DecisionReport(
            options=(option,),
            criteria=criteria,
            matrix=matrix,
            summary=summary,
            region=region,
            confidence=self._confidence(matrix),
            generated_by_llm=used_llm,
        )

    # -- internals -----------------------------------------------------------

    def _compare(
        self,
        options: tuple[str, ...],
        criteria: tuple[DynamicFactType, ...],
        region: str,
        student_context: str,
    ) -> DecisionReport:
        matrix = self._cells(options, criteria, region)
        nodes = self._nodes(options)
        summary, used_llm = self._narrate(nodes, matrix, student_context)
        return DecisionReport(
            options=options,
            criteria=criteria,
            matrix=matrix,
            summary=summary,
            region=region,
            confidence=self._confidence(matrix),
            generated_by_llm=used_llm,
        )

    def _cells(
        self,
        options: tuple[str, ...],
        criteria: tuple[DynamicFactType, ...],
        region: str,
    ) -> tuple[ComparisonCell, ...]:
        cells = []
        for option in options:
            node = self._traversal.find_by_name(option)
            subject = node.canonical_name if node else option
            for criterion in criteria:
                facts: tuple[DynamicFact, ...] = ()
                if self._dynamic is not None:
                    facts = self._dynamic.fetch_facts(subject, criterion, region)
                cells.append(ComparisonCell(subject, criterion, facts))
        return tuple(cells)

    def _nodes(self, options: tuple[str, ...]) -> tuple[Node, ...]:
        found = (self._traversal.find_by_name(o) for o in options)
        return tuple(n for n in found if n is not None)

    def _narrate(
        self,
        nodes: tuple[Node, ...],
        matrix: tuple[ComparisonCell, ...],
        student_context: str,
    ) -> tuple[str, bool]:
        facts = tuple(f for cell in matrix for f in cell.facts)
        if self._llm is not None and (nodes or facts):
            generated = self._llm.generate(
                comparison_prompt(nodes, facts, student_context)
            ).strip()
            if generated:
                return generated, True
        return self._deterministic_summary(matrix, student_context, nodes), False

    @staticmethod
    def _deterministic_summary(
        matrix: tuple[ComparisonCell, ...],
        student_context: str,
        nodes: tuple[Node, ...],
    ) -> str:
        lines = []
        for cell in matrix:
            if cell.known:
                summaries = "; ".join(f.summary for f in cell.facts)
                lines.append(f"- {cell.option} / {cell.criterion.value}: {summaries}")
            else:
                lines.append(
                    f"- {cell.option} / {cell.criterion.value}: no current data — "
                    "unknown is reported rather than invented"
                )
        # Profile-awareness without an LLM: surface which option overlaps the
        # student's stated interests.
        if student_context and nodes:
            context_tokens = tokens(student_context)
            best, best_overlap = None, 0
            for node in nodes:
                overlap = len(
                    context_tokens
                    & tokens(" ".join((node.canonical_name, node.description,
                                       *node.semantic_tags)))
                )
                if overlap > best_overlap:
                    best, best_overlap = node, overlap
            if best is not None:
                lines.append(
                    f"Closest match to your stated context: {best.canonical_name}."
                )
        return "\n".join(lines)

    @staticmethod
    def _confidence(matrix: tuple[ComparisonCell, ...]) -> Confidence:
        if not matrix:
            return Confidence.of(0.0)
        coverage = sum(1 for c in matrix if c.known) / len(matrix)
        return Confidence.of(round(0.2 + 0.7 * coverage, 4))
