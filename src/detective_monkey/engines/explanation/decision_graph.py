"""The Decision Graph (26_EXPLANATION_ENGINE.md §5, §6, §7).

The canonical, deterministic representation of *why* a recommendation exists.
Every edge represents evidence or a relationship; nothing is inferred by an LLM
(§5). The graph is auditable, reproducible and machine-readable (§27).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DecisionNodeType(str, Enum):
    """Decision graph node types (26 §6)."""

    STUDENT_CONSTRUCT = "student_construct"
    FEATURE = "feature"
    EVIDENCE = "evidence"
    SKILL = "skill"
    KNOWLEDGE_AREA = "knowledge_area"
    COMPETENCY = "competency"
    EDUCATION = "education"
    CAREER = "career"
    LABOUR_MARKET = "labour_market"
    GOAL = "goal"
    RECOMMENDATION = "recommendation"
    DIMENSION = "dimension"


class DecisionEdgeType(str, Enum):
    """Decision graph edge types (26 §7)."""

    SUPPORTED_BY = "SUPPORTED_BY"
    INFLUENCED_BY = "INFLUENCED_BY"
    REQUIRES = "REQUIRES"
    MISSING = "MISSING"
    ALIGNED_WITH = "ALIGNED_WITH"
    CONTRADICTED_BY = "CONTRADICTED_BY"
    STRENGTHENS = "STRENGTHENS"
    WEAKENS = "WEAKENS"
    DERIVED_FROM = "DERIVED_FROM"
    ADJUSTED_BY = "ADJUSTED_BY"


@dataclass(frozen=True, slots=True)
class DecisionNode:
    id: str
    node_type: DecisionNodeType
    label: str
    ref: str = ""


@dataclass(frozen=True, slots=True)
class DecisionEdge:
    source: str
    target: str
    edge_type: DecisionEdgeType
    note: str = ""


@dataclass(frozen=True, slots=True)
class DecisionGraph:
    nodes: tuple[DecisionNode, ...] = field(default_factory=tuple)
    edges: tuple[DecisionEdge, ...] = field(default_factory=tuple)

    def nodes_of(self, node_type: DecisionNodeType) -> tuple[DecisionNode, ...]:
        return tuple(n for n in self.nodes if n.node_type is node_type)
