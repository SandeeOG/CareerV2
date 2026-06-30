"""Retrieval-first and agent-orchestration tests (docs 27, 28)."""

from __future__ import annotations

from detective_monkey.contracts import EngineRequest, IntelligenceContext
from detective_monkey.domain.common.versioning import Version
from detective_monkey.domain.knowledge_graph import Node, NodeType
from detective_monkey.domain.knowledge_graph.node import NodeId
from detective_monkey.engines.agent import (
    AgentDependencies,
    AgentInput,
    CareerIntelligenceAgent,
)
from detective_monkey.engines.retrieval import (
    Intent,
    KnowledgeRetrievalEngine,
    RetrievalInput,
    SourceKind,
    classify,
)
from detective_monkey.engines.retrieval.packages import VectorHit

CTX = IntelligenceContext()


def _nodes():
    return (
        Node(NodeId("n_ds"), NodeType.CAREER, "Data Scientist", Version(1),
             description="Analyzes data with statistics", semantic_tags=("data",)),
        Node(NodeId("n_art"), NodeType.CAREER, "Visual Artist", Version(1),
             description="Creates visual art"),
    )


class _StubVectorIndex:
    def search(self, query: str, k: int):
        return [VectorHit("Course: Intro to ML", "An online ML course", 0.4, "catalog")]


def test_intent_classification():
    assert classify("Why was this recommended?") is Intent.EXPLANATION
    assert classify("What skills do i need?") is Intent.SKILL_GAP
    assert classify("Tell me about marine biology") is Intent.CAREER_EXPLORATION


def test_retrieval_prioritizes_graph_over_vector():
    resp = KnowledgeRetrievalEngine().execute(EngineRequest(CTX, RetrievalInput(
        query="Tell me about the data scientist career",
        knowledge_nodes=_nodes(),
        vector_index=_StubVectorIndex(),
    )))
    assert resp.ok
    items = resp.result.items
    assert items, "expected retrieved items"
    # The top-ranked item must be a canonical graph source, not the vector hit.
    assert items[0].kind in (SourceKind.KNOWLEDGE, SourceKind.DECISION, SourceKind.EVIDENCE)


def test_agent_explanation_without_recommendation_asks_for_clarification():
    agent = CareerIntelligenceAgent(AgentDependencies())
    resp = agent.execute(EngineRequest(CTX, AgentInput("Why was this recommended?")))
    assert resp.ok
    assert resp.result.needs_clarification is True


def test_agent_exploration_answers_from_retrieved_context():
    agent = CareerIntelligenceAgent(
        AgentDependencies(retrieval_engine=KnowledgeRetrievalEngine())
    )
    ri = RetrievalInput(query="Tell me about data scientist", knowledge_nodes=_nodes())
    resp = agent.execute(EngineRequest(CTX, AgentInput(
        "Tell me about data scientist", retrieval_input=ri,
    )))
    assert resp.ok
    assert resp.result.intent is Intent.CAREER_EXPLORATION
    assert "Data Scientist" in resp.result.response
    assert resp.result.retrieved_context is not None
