"""Graph assembly: validated knowledge becomes Knowledge Graph nodes and edges.

Ids are deterministic — node ids derive from entity slugs, edge ids from
(type, source, target) — so ingesting the same knowledge twice *updates* the
graph instead of duplicating it. That property is what makes continuous
regeneration safe. Each write emits a domain event through the publisher so
downstream features can react to knowledge growth.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...application.ports import EventPublisher, KnowledgeGraphRepository
from ...domain.common.attributes import Attributes
from ...domain.common.events import DomainEvent, EventName
from ...domain.common.identifiers import EdgeId, NodeId
from ...domain.common.versioning import Version
from ...domain.knowledge_graph.edge import Edge
from ...domain.knowledge_graph.node import Node
from ..models.entities import CandidateRelationship, CanonicalEntity, entity_node_id
from ..normalizers.text import slugify


def relationship_edge_id(
    relationship: str, source: NodeId, target: NodeId
) -> EdgeId:
    return EdgeId(f"edge_{relationship.lower()}_{source.value}__{target.value}")


@dataclass(frozen=True, slots=True)
class AssemblyResult:
    edges_written: int
    edges_skipped: int  # endpoints missing from the graph


class GraphAssembler:
    """Writes validated entities and relationships into the Knowledge Graph."""

    def __init__(
        self,
        graph: KnowledgeGraphRepository,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._graph = graph
        self._publisher = publisher

    def write_entities(self, entities: tuple[CanonicalEntity, ...]) -> int:
        for entity in entities:
            node = entity.to_node()
            existing = self._graph.get_node(node.id.value)
            if existing is not None:
                # Preserve version monotonicity across regeneration runs.
                node = self._reversioned(entity, existing.version.next("regenerated"))
            self._graph.add_node(node)
            self._publish(EventName.KNOWLEDGE_IMPORTED, node.id.value, "node",
                          Attributes.of(name=entity.canonical_name,
                                        type=entity.entity_type.value))
        return len(entities)

    def write_relationships(
        self,
        relationships: tuple[CandidateRelationship, ...],
        entities: tuple[CanonicalEntity, ...],
    ) -> AssemblyResult:
        # Resolve names (canonical or alias) to node ids.
        by_slug: dict[str, CanonicalEntity] = {}
        for entity in entities:
            by_slug[entity.slug] = entity
            for alias in entity.aliases:
                by_slug.setdefault(slugify(alias), entity)
        # Include entities already in the graph from earlier runs.
        stored: dict[str, NodeId] = {}
        for node in self._graph.list_nodes():
            stored.setdefault(slugify(node.canonical_name), node.id)
            for alias in node.aliases:
                stored.setdefault(slugify(alias), node.id)

        written = skipped = 0
        for rel in relationships:
            source_id = self._resolve(rel.source_name, by_slug, stored)
            target_id = self._resolve(rel.target_name, by_slug, stored)
            if source_id is None or target_id is None or source_id == target_id:
                skipped += 1
                continue
            edge = Edge(
                id=relationship_edge_id(rel.relationship.value, source_id, target_id),
                edge_type=rel.relationship,
                source=source_id,
                target=target_id,
                version=Version(1, "generated"),
                strength=rel.strength,
                confidence=rel.confidence,
            )
            self._graph.add_edge(edge)
            self._publish(EventName.KNOWLEDGE_LINKED, edge.id.value, "edge",
                          Attributes.of(relationship=rel.relationship.value,
                                        source=rel.source_name,
                                        target=rel.target_name))
            written += 1
        return AssemblyResult(written, skipped)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _resolve(
        name: str,
        entities: dict[str, CanonicalEntity],
        stored: dict[str, NodeId],
    ) -> NodeId | None:
        # Prefer ids of nodes already in the graph: they are authoritative even
        # for nodes created outside the platform (whose ids are not slug-derived).
        slug = slugify(name)
        node_id = stored.get(slug)
        if node_id is not None:
            return node_id
        entity = entities.get(slug)
        if entity is not None:
            return entity_node_id(entity.entity_type, entity.slug)
        return None

    @staticmethod
    def _reversioned(entity: CanonicalEntity, version: Version) -> Node:
        base = entity.to_node()
        return Node(
            id=base.id,
            node_type=base.node_type,
            canonical_name=base.canonical_name,
            version=version,
            description=base.description,
            aliases=base.aliases,
            semantic_tags=base.semantic_tags,
            status=base.status,
            verification_status=base.verification_status,
            quality_score=base.quality_score,
            coverage_score=base.coverage_score,
            provenance=base.provenance,
            metadata=base.metadata,
        )

    def _publish(
        self, name: EventName, aggregate_id: str, aggregate_type: str,
        payload: Attributes,
    ) -> None:
        if self._publisher is not None:
            self._publisher.publish(
                DomainEvent(name=name, aggregate_id=aggregate_id,
                            aggregate_type=aggregate_type, payload=payload)
            )
