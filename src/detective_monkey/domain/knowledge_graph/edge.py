"""Knowledge Graph edge (17_KNOWLEDGE_GRAPH.md §9).

Relationships are first-class entities (17 §4 GP-03), independently versioned
(§21 INV-05), each carrying an explicit semantic type, strength, weight,
confidence and traceable evidence (§11 Evidence Layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.attributes import Attributes
from ..common.confidence import Confidence
from ..common.identifiers import EdgeId, EvidenceId, NodeId
from ..common.scores import UnitInterval
from ..common.versioning import Version
from .ontology import EdgeDirection, RelationshipType


@dataclass(frozen=True, slots=True)
class Edge:
    """An immutable, versioned, evidence-backed relationship between two nodes.

    ``strength`` expresses how strong the semantic relationship is; ``weight``
    is a separate quantity available to traversal/scoring (17 §9). Both are
    optional because, per INV-08-style reasoning, an unknown strength must not
    be fabricated as zero.
    """

    id: EdgeId
    edge_type: RelationshipType
    source: NodeId
    target: NodeId
    version: Version
    direction: EdgeDirection = EdgeDirection.DIRECTED
    strength: UnitInterval | None = None
    weight: UnitInterval | None = None
    confidence: Confidence | None = None
    evidence: tuple[EvidenceId, ...] = field(default_factory=tuple)
    metadata: Attributes = field(default_factory=Attributes)

    def __post_init__(self) -> None:
        if self.source == self.target:
            raise ValueError("Edge.source and Edge.target must differ (no self-loops)")

    def reversed(self, new_id: EdgeId) -> "Edge":
        """Return the reverse of an undirected edge for traversal convenience."""
        if self.direction is not EdgeDirection.UNDIRECTED:
            raise ValueError("Only undirected edges may be reversed")
        return Edge(
            id=new_id,
            edge_type=self.edge_type,
            source=self.target,
            target=self.source,
            version=self.version,
            direction=self.direction,
            strength=self.strength,
            weight=self.weight,
            confidence=self.confidence,
            evidence=self.evidence,
            metadata=self.metadata,
        )
