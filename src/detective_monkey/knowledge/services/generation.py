"""KnowledgeGenerationService — the ingest/generate/validate/store loop.

The service that makes Detective Monkey a knowledge *platform* instead of a
maintained database:

    sources.fetch -> source.normalize -> source.validate
    -> canonicalize + merge duplicates
    -> generate relationships (hints, heuristics, optional LLM)
    -> validation pipeline (only validated knowledge enters the graph)
    -> graph assembly (idempotent upserts)

``ingest_all`` is a full generation run; ``enrich_missing`` is the continuous
improvement pass that fills sparse descriptions and proposes new relationships
for under-connected nodes. Both are designed to run as background jobs — they
never sit on a user-facing request path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...application.ports import EventPublisher, KnowledgeGraphRepository
from ...domain.common.confidence import Confidence
from ...domain.common.provenance import Provenance, SourceType
from ...domain.knowledge_graph.node import Node
from ...domain.knowledge_graph.ontology import NodeStatus, NodeType
from ..generators.heuristics import (
    industry_mappings,
    learning_path,
    relate_by_shared_links,
    relationships_from_hints,
)
from ..generators.llm import LLMPort, StructuredGenerator
from ..graph.builder import GraphAssembler
from ..graph.traversal import GraphTraversal
from ..models.entities import CandidateRelationship, CanonicalEntity
from ..models.records import RawKnowledgeRecord, SourceMetadata
from ..normalizers.canonicalizer import Canonicalizer, EntityMerger
from ..normalizers.text import slugify
from ..sources.base import KnowledgeSource, SourceRegistry
from ..validators.checks import ValidationIssue, check_conflicts
from ..validators.pipeline import ValidationPipeline


@dataclass(frozen=True, slots=True)
class GenerationReport:
    """What one generation run did — the audit trail of knowledge growth."""

    records_fetched: int = 0
    entities_accepted: int = 0
    entities_rejected: int = 0
    relationships_accepted: int = 0
    relationships_rejected: int = 0
    edges_written: int = 0
    edges_skipped: int = 0
    descriptions_enriched: int = 0
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)


class KnowledgeGenerationService:
    """Generates, validates and stores canonical knowledge."""

    def __init__(
        self,
        registry: SourceRegistry,
        graph: KnowledgeGraphRepository,
        *,
        canonicalizer: Canonicalizer | None = None,
        validation: ValidationPipeline | None = None,
        llm: LLMPort | None = None,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._registry = registry
        self._graph = graph
        self._canonicalizer = canonicalizer or Canonicalizer()
        self._merger = EntityMerger(self._canonicalizer)
        self._validation = validation or ValidationPipeline()
        self._generator = StructuredGenerator(llm)
        self._assembler = GraphAssembler(graph, publisher)
        self._traversal = GraphTraversal(graph)

    # -- generation runs ------------------------------------------------------

    def ingest_all(self) -> GenerationReport:
        """Run the full loop over every registered source."""
        return self._ingest(self._registry.list_all())

    def ingest(self, source_id: str) -> GenerationReport:
        source = self._registry.get(source_id)
        if source is None:
            raise KeyError(f"unknown knowledge source: {source_id!r}")
        return self._ingest((source,))

    def _ingest(self, sources: tuple[KnowledgeSource, ...]) -> GenerationReport:
        source_meta: dict[str, SourceMetadata] = {}
        records: list[RawKnowledgeRecord] = []
        for source in sources:
            meta = source.metadata()
            source_meta[meta.source_id] = meta
            fetched = source.fetch()
            records.extend(source.validate(source.normalize(fetched)))

        raw = tuple(records)
        entities = self._merger.merge(raw, source_meta)

        # Cross-source conflict detection (kept, flagged for curation).
        conflict_issues = self._conflicts(raw)

        entity_report = self._validation.validate_entities(entities)
        accepted = entity_report.accepted

        relationships = self._generate_relationships(raw, accepted)
        rel_report = self._validation.validate_relationships(relationships, accepted)

        self._assembler.write_entities(accepted)
        assembly = self._assembler.write_relationships(rel_report.accepted, accepted)

        return GenerationReport(
            records_fetched=len(raw),
            entities_accepted=len(accepted),
            entities_rejected=len(entity_report.rejected),
            relationships_accepted=len(rel_report.accepted),
            relationships_rejected=len(rel_report.rejected),
            edges_written=assembly.edges_written,
            edges_skipped=assembly.edges_skipped,
            issues=tuple(conflict_issues)
            + entity_report.issues
            + rel_report.issues,
        )

    def _generate_relationships(
        self,
        raw: tuple[RawKnowledgeRecord, ...],
        entities: tuple[CanonicalEntity, ...],
    ) -> tuple[CandidateRelationship, ...]:
        candidates: list[CandidateRelationship] = []
        candidates.extend(
            relationships_from_hints(raw, self._canonicalizer.resolve)
        )
        candidates.extend(relate_by_shared_links(entities, tuple(candidates)))
        candidates.extend(industry_mappings(entities))
        return tuple(candidates)

    def _conflicts(
        self, raw: tuple[RawKnowledgeRecord, ...]
    ) -> list[ValidationIssue]:
        groups: dict[str, list[RawKnowledgeRecord]] = {}
        for record in raw:
            canonical = self._canonicalizer.resolve(record.name, record.entity_type)
            groups.setdefault(canonical, []).append(record)
        issues: list[ValidationIssue] = []
        for canonical, group in sorted(groups.items()):
            if len(group) > 1:
                issues.extend(check_conflicts(canonical, tuple(group)))
        return issues

    # -- continuous enrichment --------------------------------------------------

    def enrich_missing(self, limit: int = 20) -> GenerationReport:
        """Fill sparse descriptions and propose relationships for lonely nodes.

        LLM output never lands directly: descriptions are shape-checked by the
        generator and relationship proposals pass the validation pipeline (the
        LLM may only link entities that already exist).
        """
        nodes = self._graph.list_nodes()
        enriched = 0
        proposals: list[CandidateRelationship] = []
        known_entities = self._as_entities(nodes)

        for node in sorted(nodes, key=lambda n: n.canonical_name)[: max(0, limit)]:
            related = self._traversal.neighbours(node.id.value)
            if not node.description and self._generator.available:
                description = self._generator.propose_description(node, related)
                if description:
                    self._graph.add_node(self._with_description(node, description))
                    enriched += 1
            if not related and self._generator.available:
                others = tuple(n for n in nodes if n.id != node.id)[:30]
                proposals.extend(
                    self._generator.propose_relationships(node, others)
                )

        rel_report = self._validation.validate_relationships(
            tuple(proposals), known_entities
        )
        assembly = self._assembler.write_relationships(
            rel_report.accepted, known_entities
        )
        return GenerationReport(
            descriptions_enriched=enriched,
            relationships_accepted=len(rel_report.accepted),
            relationships_rejected=len(rel_report.rejected),
            edges_written=assembly.edges_written,
            edges_skipped=assembly.edges_skipped,
            issues=rel_report.issues,
        )

    # -- derived knowledge (used by discovery/roadmaps) --------------------------

    def learning_path_for(self, career_name: str) -> tuple[Node, ...]:
        career = self._traversal.find_by_name(career_name)
        if career is None:
            return ()
        skills = self._traversal.neighbours(
            career.id.value, node_types=frozenset({NodeType.SKILL})
        )
        return learning_path(career, skills)

    # -- helpers ------------------------------------------------------------------

    @staticmethod
    def _as_entities(nodes: tuple[Node, ...]) -> tuple[CanonicalEntity, ...]:
        """Project stored nodes back into entities for validation resolution."""
        out = []
        for node in nodes:
            out.append(
                CanonicalEntity(
                    id=node.id,
                    entity_type=node.node_type,
                    canonical_name=node.canonical_name,
                    slug=slugify(node.canonical_name),
                    version=node.version,
                    description=node.description,
                    aliases=node.aliases,
                    tags=node.semantic_tags,
                    attributes=node.metadata,
                    confidence=Confidence.of(
                        node.quality_score.value if node.quality_score else 0.5
                    ),
                    provenance=node.provenance
                    or Provenance(SourceType.SYSTEM, "stored node"),
                )
            )
        return tuple(out)

    @staticmethod
    def _with_description(node: Node, description: str) -> Node:
        return Node(
            id=node.id,
            node_type=node.node_type,
            canonical_name=node.canonical_name,
            version=node.version.next("enriched"),
            description=description,
            aliases=node.aliases,
            semantic_tags=node.semantic_tags,
            status=NodeStatus.PUBLISHED,
            verification_status=node.verification_status,
            quality_score=node.quality_score,
            coverage_score=node.coverage_score,
            provenance=Provenance(
                SourceType.DERIVED, "description enriched by validated LLM generation",
                references=node.provenance.references if node.provenance else (),
            ),
            metadata=node.metadata,
        )
