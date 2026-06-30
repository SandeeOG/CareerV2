"""Knowledge Graph node (17_KNOWLEDGE_GRAPH.md §8).

Every node represents exactly one concept (17 §4 GP-01) and is independently
versioned and immutable (17 §21 INV-04). Canonical knowledge entities (skills,
careers, subjects, ...) are projections over nodes; this is the lowest-level
graph primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.attributes import Attributes
from ..common.identifiers import NodeId
from ..common.provenance import Provenance
from ..common.scores import UnitInterval
from ..common.versioning import Version
from .ontology import NodeStatus, NodeType, VerificationStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Node:
    """An immutable, versioned graph node.

    Identity (§8): a node has one canonical name and may have aliases. Semantic
    tags (§8 "Semantic Tags") improve search. Quality and coverage scores live
    in metadata-style fields so the graph can express how well a concept is
    described.
    """

    id: NodeId
    node_type: NodeType
    canonical_name: str
    version: Version
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    semantic_tags: tuple[str, ...] = field(default_factory=tuple)
    status: NodeStatus = NodeStatus.DRAFT
    verification_status: VerificationStatus = VerificationStatus.PROVISIONAL
    quality_score: UnitInterval | None = None
    coverage_score: UnitInterval | None = None
    provenance: Provenance | None = None
    metadata: Attributes = field(default_factory=Attributes)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.canonical_name or not self.canonical_name.strip():
            raise ValueError("Node.canonical_name must be a non-empty string")
