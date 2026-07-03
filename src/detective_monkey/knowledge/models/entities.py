"""Canonical knowledge entities and candidate relationships.

A `CanonicalEntity` is the merged, validated form of one concept across all
sources ("Software Developer", "Programmer" and "Backend Engineer" collapse to
one "Software Engineer" entity carrying the others as aliases). Its identifier
is *derived from the slug*, so re-ingesting the same concept updates rather
than duplicates — the property that lets knowledge grow continuously.

Canonical entities project onto Knowledge Graph nodes (17 §21 INV-01: every
concept maps to exactly one canonical node); `to_node` is that projection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.attributes import Attributes
from ...domain.common.confidence import Confidence
from ...domain.common.identifiers import NodeId
from ...domain.common.provenance import Provenance
from ...domain.common.scores import UnitInterval
from ...domain.common.versioning import Version
from ...domain.knowledge_graph.node import Node
from ...domain.knowledge_graph.ontology import (
    NodeStatus,
    NodeType,
    RelationshipType,
    VerificationStatus,
)
from .layers import KnowledgeLayer


def entity_node_id(entity_type: NodeType, slug: str) -> NodeId:
    """Deterministic node id: one concept, one id, across every ingestion run."""
    return NodeId(f"node_{entity_type.value}_{slug}")


@dataclass(frozen=True, slots=True)
class CanonicalEntity:
    """One validated concept, merged across sources."""

    id: NodeId
    entity_type: NodeType
    canonical_name: str
    slug: str
    version: Version
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    attributes: Attributes = field(default_factory=Attributes)
    layer: KnowledgeLayer = KnowledgeLayer.CORE
    external_codes: tuple[str, ...] = field(default_factory=tuple)
    confidence: Confidence | None = None
    provenance: Provenance | None = None
    verification_status: VerificationStatus = VerificationStatus.PROVISIONAL

    def __post_init__(self) -> None:
        if not self.canonical_name.strip():
            raise ValueError("CanonicalEntity.canonical_name must be non-empty")
        if not self.slug.strip():
            raise ValueError("CanonicalEntity.slug must be non-empty")
        if self.layer is not KnowledgeLayer.CORE:
            raise ValueError(
                "Only core knowledge becomes a canonical entity; dynamic facts "
                "belong in DynamicFact and personalized output is never stored"
            )

    def to_node(self) -> Node:
        """Project this entity onto its canonical Knowledge Graph node."""
        quality = self.confidence.value if self.confidence else None
        return Node(
            id=self.id,
            node_type=self.entity_type,
            canonical_name=self.canonical_name,
            version=self.version,
            description=self.description,
            aliases=self.aliases,
            semantic_tags=self.tags,
            status=NodeStatus.PUBLISHED,
            verification_status=self.verification_status,
            quality_score=quality,
            provenance=self.provenance,
            metadata=self.attributes,
        )


@dataclass(frozen=True, slots=True)
class CandidateRelationship:
    """A proposed relationship between two canonical entities, by name.

    Candidates come from source hints, deterministic heuristics or the LLM;
    all of them pass the validation pipeline before becoming graph edges.
    """

    relationship: RelationshipType
    source_name: str
    target_name: str
    strength: UnitInterval | None = None
    confidence: Confidence | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not self.source_name.strip() or not self.target_name.strip():
            raise ValueError("CandidateRelationship endpoints must be non-empty")
