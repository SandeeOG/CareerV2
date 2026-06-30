"""Knowledge Retrieval Engine (27_KNOWLEDGE_RETRIEVAL_ARCHITECTURE.md).

Retrieval-first: structured retrieval over the Knowledge, Evidence, Decision and
Memory graphs precedes any optional vector expansion, then a deterministic prompt
is assembled (§2, §4). The Knowledge Graph is authoritative (INV-01); vector
search never overrides canonical knowledge (INV-05); prompt assembly is
deterministic (INV-07) and the LLM never retrieves directly (INV-06).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...contracts import (
    BaseEngine,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    IntelligenceLayer,
)
from ...domain.common.confidence import Confidence
from ...domain.common.scores import Importance
from ...domain.common.versioning import Version
from ...domain.knowledge_graph.node import Node
from ...domain.memory.memory import Memory
from ..evidence.graph import EvidenceGraph
from ..explanation.decision_graph import DecisionGraph
from .intent import Intent, classify
from .packages import (
    SOURCE_PRIORITY,
    ContextPackage,
    PromptSection,
    RetrievalPromptPackage,
    RetrievedItem,
    SourceKind,
    VectorIndex,
)

ENGINE_VERSION = Version(1, "P2")
_PROMPT_TEMPLATE_VERSION = "retrieval-prompt-v1"
_MIN_RELEVANCE = 0.05
_DEFAULT_BUDGET = 12

_STOPWORDS = frozenset(
    {"the", "a", "an", "is", "are", "do", "i", "me", "my", "to", "of", "for",
     "what", "which", "and", "or", "should", "can", "you", "about", "in", "on"}
)
_IMPORTANCE_BOOST = {
    Importance.CRITICAL: 1.0,
    Importance.HIGH: 0.8,
    Importance.MEDIUM: 0.5,
    Importance.LOW: 0.3,
    Importance.TEMPORARY: 0.1,
}


@dataclass(frozen=True, slots=True)
class RetrievalInput:
    query: str
    knowledge_nodes: tuple[Node, ...] = field(default_factory=tuple)
    evidence_graph: EvidenceGraph | None = None
    decision_graph: DecisionGraph | None = None
    memories: tuple[Memory, ...] = field(default_factory=tuple)
    vector_index: VectorIndex | None = None
    intent_override: Intent | None = None
    max_items: int = _DEFAULT_BUDGET


class KnowledgeRetrievalEngine(BaseEngine[RetrievalInput, ContextPackage]):
    """Deterministic, graph-first retrieval (27 §1)."""

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="knowledge_retrieval_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.KNOWLEDGE,
            description="Retrieval-first context assembly for the AI layer.",
        )

    def _run(self, request: EngineRequest[RetrievalInput]) -> EngineOutcome[ContextPackage]:
        payload = request.payload
        intent = payload.intent_override or classify(payload.query)
        tokens = self._tokens(payload.query)

        items: list[RetrievedItem] = []

        # 1. Decision Graph (authoritative for reasoning, highest priority).
        if payload.decision_graph is not None:
            items.extend(self._from_decision(payload.decision_graph, tokens))
        # 2. Knowledge Graph (authoritative facts).
        items.extend(self._from_knowledge(payload.knowledge_nodes, tokens))
        # 3. Evidence Graph (observations).
        if payload.evidence_graph is not None:
            items.extend(self._from_evidence(payload.evidence_graph, tokens))
        # 4. Memory (continuity).
        items.extend(self._from_memory(payload.memories, tokens))
        # 5. Vector expansion (supplements; never primary).
        if payload.vector_index is not None:
            for hit in payload.vector_index.search(payload.query, k=5):
                items.append(
                    RetrievedItem(SourceKind.VECTOR, hit.label, hit.content,
                                  max(0.0, min(1.0, hit.similarity)), hit.provenance)
                )

        # Validation + ranking + budget (27 §12, §14, §20).
        items = [i for i in items if i.relevance >= _MIN_RELEVANCE]
        items = self._dedupe(items)
        items.sort(key=lambda i: (SOURCE_PRIORITY[i.kind], i.relevance, i.label),
                   reverse=True)
        kept = items[: max(0, payload.max_items)]

        prompt = self._assemble_prompt(intent, payload.query, kept)
        confidence = (
            sum(i.relevance for i in kept) / len(kept) if kept else 0.0
        )
        package = ContextPackage(intent=intent.value, items=tuple(kept), prompt=prompt)
        return EngineOutcome(
            result=package,
            confidence=Confidence.of(confidence),
            metrics={
                "intent": intent.value,
                "retrieved": str(len(items)),
                "kept": str(len(kept)),
            },
        )

    # -- per-source retrieval ----------------------------------------------

    def _from_knowledge(self, nodes: tuple[Node, ...], tokens: set[str]) -> list[RetrievedItem]:
        out = []
        for n in nodes:
            text = " ".join((n.canonical_name, *n.aliases, *n.semantic_tags))
            rel = self._relevance(tokens, text)
            if rel > 0:
                out.append(
                    RetrievedItem(SourceKind.KNOWLEDGE, n.canonical_name,
                                  n.description or n.canonical_name, rel,
                                  provenance=n.node_type.value)
                )
        return out

    def _from_evidence(self, graph: EvidenceGraph, tokens: set[str]) -> list[RetrievedItem]:
        out = []
        for e in graph.evidence:
            rel = self._relevance(tokens, f"{e.subject} {e.summary}")
            if rel > 0:
                out.append(
                    RetrievedItem(SourceKind.EVIDENCE, e.subject, e.summary, rel,
                                  provenance=e.provenance.source.value)
                )
        return out

    def _from_decision(self, graph: DecisionGraph, tokens: set[str]) -> list[RetrievedItem]:
        out = []
        for node in graph.nodes:
            rel = self._relevance(tokens, node.label)
            # Decision reasoning is always at least mildly relevant to a query.
            rel = max(rel, 0.2)
            out.append(
                RetrievedItem(SourceKind.DECISION, node.label, node.label, rel,
                              provenance=node.node_type.value)
            )
        return out

    def _from_memory(self, memories: tuple[Memory, ...], tokens: set[str]) -> list[RetrievedItem]:
        out = []
        for m in memories:
            base = self._relevance(tokens, m.summary)
            rel = min(1.0, base + 0.2 * _IMPORTANCE_BOOST.get(m.importance, 0.5))
            if rel > 0:
                out.append(
                    RetrievedItem(SourceKind.MEMORY, m.memory_type.value, m.summary, rel,
                                  provenance=m.provenance.source.value)
                )
        return out

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _tokens(text: str) -> set[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return {w for w in words if w not in _STOPWORDS}

    def _relevance(self, query_tokens: set[str], text: str) -> float:
        if not query_tokens:
            return 0.0
        text_tokens = self._tokens(text)
        if not text_tokens:
            return 0.0
        overlap = len(query_tokens & text_tokens)
        return overlap / len(query_tokens)

    @staticmethod
    def _dedupe(items: list[RetrievedItem]) -> list[RetrievedItem]:
        seen: set[tuple[str, str]] = set()
        out = []
        for i in items:
            key = (i.kind.value, i.label)
            if key in seen:
                continue
            seen.add(key)
            out.append(i)
        return out

    @staticmethod
    def _assemble_prompt(
        intent: Intent, query: str, items: list[RetrievedItem]
    ) -> RetrievalPromptPackage:
        sections = []
        for kind in (SourceKind.DECISION, SourceKind.KNOWLEDGE, SourceKind.EVIDENCE,
                     SourceKind.MEMORY, SourceKind.VECTOR):
            group = [i for i in items if i.kind is kind]
            if group:
                sections.append(
                    PromptSection(
                        kind.value.title(),
                        "\n".join(f"- {i.label}: {i.content}" for i in group),
                    )
                )
        system = (
            "Answer using ONLY the retrieved context below. The Knowledge Graph and "
            "Decision Graph are authoritative; never contradict them or invent facts."
        )
        return RetrievalPromptPackage(
            system_prompt=system,
            sections=tuple(sections),
            user_question=query,
            template_version=_PROMPT_TEMPLATE_VERSION,
        )
