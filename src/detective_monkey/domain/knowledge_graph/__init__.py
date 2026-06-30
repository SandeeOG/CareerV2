"""Knowledge Graph domain primitives (17_KNOWLEDGE_GRAPH.md).

The canonical semantic model: nodes (concepts) and edges (relationships), both
first-class, versioned and immutable. Higher domain modules (skills, career,
education, ...) define richer projections, but every concept ultimately maps to
exactly one canonical node here (17 §21 INV-01).
"""

from .edge import Edge
from .node import Node
from .ontology import (
    EdgeDirection,
    NodeStatus,
    NodeType,
    RelationshipType,
    VerificationStatus,
)

__all__ = [
    "Edge",
    "Node",
    "EdgeDirection",
    "NodeStatus",
    "NodeType",
    "RelationshipType",
    "VerificationStatus",
]
