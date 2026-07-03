"""The knowledge retrieval pipeline.

    User Question -> Intent Detection -> Knowledge Retrieval -> Graph Expansion
    -> Dynamic Retrieval -> LLM Reasoning -> Final Answer

Retrieval always comes first; the LLM only *reasons over* what was retrieved
and is never allowed to invent factual career data. Without a provider the
pipeline still answers, deterministically, from the retrieved knowledge —
grounding is a property of the pipeline, not of the model. Dynamic facts are
fetched through the provider port and cached; regional queries never require
regionally-materialized careers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.confidence import Confidence, ConfidenceFactor
from ...domain.common.provenance import Provenance, SourceType
from ...domain.common.scores import UnitInterval
from ...domain.knowledge_graph.node import Node
from ...domain.knowledge_graph.ontology import NodeType
from ..cache.cache import KnowledgeCache
from ..generators.llm import LLMPort
from ..graph.traversal import GraphTraversal, Subgraph
from ..models.dynamic import DEFAULT_FACT_TTL, DynamicFact, DynamicFactType
from ..normalizers.text import slugify
from ..prompts.templates import answer_prompt
from ..sources.dynamic import DynamicKnowledgeProvider
from .intent import KnowledgeIntent, classify, extract_region, requested_fact_types

_MAX_SEEDS = 5
_EXPANSION_DEPTH = 1
_NEGATIVE_CACHE_TTL = 300  # "no facts known" is retried after a short while


@dataclass(frozen=True, slots=True)
class KnowledgeAnswer:
    """The pipeline output: a grounded answer plus everything it was built from."""

    query: str
    intent: KnowledgeIntent
    answer: str
    nodes: tuple[Node, ...] = field(default_factory=tuple)
    expanded: Subgraph = field(default_factory=Subgraph)
    facts: tuple[DynamicFact, ...] = field(default_factory=tuple)
    region: str = ""
    confidence: Confidence | None = None
    provenance: Provenance | None = None
    generated_by_llm: bool = False


class KnowledgeRetrievalPipeline:
    """Retrieval-first question answering over the Knowledge Platform."""

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

    def answer(self, query: str, student_context: str = "") -> KnowledgeAnswer:
        # 1. Intent detection.
        intent = classify(query)

        # 2. Knowledge retrieval (graph is authoritative).
        seeds = self._traversal.search(query, limit=_MAX_SEEDS)

        # 3. Graph expansion.
        expanded = self._traversal.expand(
            tuple(n.id.value for n in seeds), depth=_EXPANSION_DEPTH
        )

        # 4. Dynamic retrieval (cached; Layer 2 is fetched, never stored).
        region = self._region_of(query)
        facts = self._dynamic_facts(query, intent, seeds, region)

        # 5. LLM reasoning over retrieved context only; deterministic fallback.
        context_nodes = self._merge_nodes(seeds, expanded.nodes)
        text, used_llm = self._reason(query, context_nodes, facts, student_context)

        confidence = self._confidence(seeds, facts)
        provenance = Provenance(
            SourceType.DERIVED,
            "knowledge retrieval pipeline",
            references=tuple(n.id.value for n in context_nodes)
            + tuple(f"{f.fact_type.value}:{slugify(f.subject)}" for f in facts),
        )
        return KnowledgeAnswer(
            query=query,
            intent=intent,
            answer=text,
            nodes=context_nodes,
            expanded=expanded,
            facts=facts,
            region=region,
            confidence=confidence,
            provenance=provenance,
            generated_by_llm=used_llm,
        )

    # -- stages ---------------------------------------------------------------

    def _region_of(self, query: str) -> str:
        regions = tuple(
            n.canonical_name
            for n in self._traversal.search(query, limit=20)
            if n.node_type in (NodeType.COUNTRY, NodeType.REGION)
        )
        return extract_region(query, regions)

    def _dynamic_facts(
        self,
        query: str,
        intent: KnowledgeIntent,
        seeds: tuple[Node, ...],
        region: str,
    ) -> tuple[DynamicFact, ...]:
        if self._dynamic is None:
            return ()
        fact_types = requested_fact_types(query)
        if not fact_types and intent in (KnowledgeIntent.REGIONAL, KnowledgeIntent.FACT):
            fact_types = (DynamicFactType.DEMAND, DynamicFactType.SALARY)
        if not fact_types:
            return ()

        subjects = [
            n.canonical_name for n in seeds
            if n.node_type not in (NodeType.COUNTRY, NodeType.REGION)
        ]
        facts: list[DynamicFact] = []
        for subject in subjects[:3]:
            for fact_type in fact_types:
                key = KnowledgeCache.key(
                    "dynamic", slugify(subject), fact_type.value, slugify(region)
                )
                cached = self._cache.get(key)
                if cached is not None:
                    facts.extend(cached)  # type: ignore[arg-type]
                    continue
                fetched = self._dynamic.fetch_facts(subject, fact_type, region)
                ttl = (
                    min(min(f.ttl_seconds for f in fetched), DEFAULT_FACT_TTL[fact_type])
                    if fetched
                    else _NEGATIVE_CACHE_TTL
                )
                self._cache.put(key, fetched, ttl)
                facts.extend(fetched)
        return tuple(facts)

    def _reason(
        self,
        query: str,
        nodes: tuple[Node, ...],
        facts: tuple[DynamicFact, ...],
        student_context: str,
    ) -> tuple[str, bool]:
        if self._llm is not None and (nodes or facts):
            generated = self._llm.generate(
                answer_prompt(query, nodes, facts, student_context)
            ).strip()
            if generated:
                return generated, True
        return self._deterministic_answer(query, nodes, facts), False

    @staticmethod
    def _deterministic_answer(
        query: str, nodes: tuple[Node, ...], facts: tuple[DynamicFact, ...]
    ) -> str:
        if not nodes and not facts:
            return (
                "No canonical knowledge matched this question yet. The knowledge "
                "base grows continuously — try related terms, or ask about a "
                "career, skill or place the platform already knows."
            )
        lines = []
        if nodes:
            lines.append("What the knowledge base says:")
            lines.extend(
                f"- {n.canonical_name}: {n.description or 'a ' + n.node_type.value + ' in the knowledge graph'}"
                for n in nodes[:6]
            )
        if facts:
            lines.append("Current facts (retrieved, time-limited):")
            lines.extend(
                f"- {f.subject}{' in ' + f.region if f.region else ''} "
                f"[{f.fact_type.value}]: {f.summary}"
                for f in facts[:6]
            )
        return "\n".join(lines)

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _merge_nodes(
        seeds: tuple[Node, ...], expanded: tuple[Node, ...]
    ) -> tuple[Node, ...]:
        seen: dict[str, Node] = {}
        for node in (*seeds, *expanded):
            seen.setdefault(node.id.value, node)
        return tuple(seen.values())

    @staticmethod
    def _confidence(
        seeds: tuple[Node, ...], facts: tuple[DynamicFact, ...]
    ) -> Confidence:
        coverage = min(1.0, len(seeds) / _MAX_SEEDS)
        factors = [
            ConfidenceFactor(
                "retrieval_coverage", UnitInterval(coverage),
                f"{len(seeds)} canonical matches",
            )
        ]
        freshness_bonus = 0.1 if facts else 0.0
        if facts:
            factors.append(
                ConfidenceFactor(
                    "dynamic_facts", UnitInterval(freshness_bonus),
                    f"{len(facts)} fresh dynamic facts retrieved",
                )
            )
        value = min(1.0, 0.2 + 0.6 * coverage + freshness_bonus)
        return Confidence(UnitInterval(value), tuple(factors))
