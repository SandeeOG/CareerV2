"""Deterministic knowledge generators.

The baseline generators: they derive relationships, mappings, summaries and
learning paths from structure that already exists in the validated records —
no LLM involved, fully reproducible. The LLM generator supplements these; it
never replaces them, so the platform keeps generating knowledge even with no
provider configured.
"""

from __future__ import annotations

from typing import Callable

from ...domain.common.confidence import Confidence
from ...domain.common.provenance import Provenance, SourceType
from ...domain.common.scores import UnitInterval
from ...domain.knowledge_graph.node import Node
from ...domain.knowledge_graph.ontology import NodeType, RelationshipType
from ..models.entities import CandidateRelationship, CanonicalEntity
from ..models.records import RawKnowledgeRecord
from ..normalizers.text import slugify

_DERIVED = Provenance(SourceType.DERIVED, "deterministic heuristic generator")


def relationships_from_hints(
    records: tuple[RawKnowledgeRecord, ...],
    resolve: Callable[[str, NodeType], str],
) -> tuple[CandidateRelationship, ...]:
    """Turn source-asserted relationship hints into candidates.

    ``resolve`` is the canonicalizer's resolve function, so hints pointing at
    "Programmer" land on "Software Engineer".
    """
    out = []
    for record in records:
        source_name = resolve(record.name, record.entity_type)
        for hint in record.relationships:
            out.append(
                CandidateRelationship(
                    relationship=hint.relationship,
                    source_name=source_name,
                    target_name=resolve(hint.target_name, hint.target_type),
                    strength=hint.strength,
                    confidence=Confidence.of(0.7),
                    provenance=Provenance(
                        SourceType.EXTERNAL_INTEGRATION,
                        f"asserted by source {record.source_id}",
                        references=(record.source_id,),
                    ),
                )
            )
    return tuple(out)


def relate_by_shared_links(
    entities: tuple[CanonicalEntity, ...],
    relationships: tuple[CandidateRelationship, ...],
    *,
    entity_type: NodeType = NodeType.CAREER,
    via: RelationshipType = RelationshipType.REQUIRES,
    min_overlap: float = 0.4,
) -> tuple[CandidateRelationship, ...]:
    """Careers sharing skills become RELATED_TO — the "related careers" generator.

    Overlap is Jaccard over each pair's ``via`` targets (e.g. required skills).
    """
    targets: dict[str, frozenset[str]] = {}
    for entity in entities:
        if entity.entity_type is not entity_type:
            continue
        linked = frozenset(
            r.target_name for r in relationships
            if r.relationship is via and r.source_name == entity.canonical_name
        )
        if linked:
            targets[entity.canonical_name] = linked

    out = []
    names = sorted(targets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = len(targets[a] & targets[b]) / len(targets[a] | targets[b])
            if overlap >= min_overlap:
                out.append(
                    CandidateRelationship(
                        relationship=RelationshipType.RELATED_TO,
                        source_name=a,
                        target_name=b,
                        strength=UnitInterval(round(overlap, 4)),
                        confidence=Confidence.of(min(1.0, 0.4 + overlap / 2)),
                        provenance=_DERIVED,
                    )
                )
    return tuple(out)


def industry_mappings(
    entities: tuple[CanonicalEntity, ...],
) -> tuple[CandidateRelationship, ...]:
    """Careers carrying an ``industry`` attribute or industry tag → BELONGS_TO."""
    industries = {
        e.slug: e.canonical_name
        for e in entities
        if e.entity_type is NodeType.INDUSTRY
    }
    out = []
    for entity in entities:
        if entity.entity_type is not NodeType.CAREER:
            continue
        declared = entity.attributes.get("industry")
        candidates = [declared] if declared else []
        candidates.extend(t for t in entity.tags)
        for candidate in candidates:
            slug = slugify(candidate or "")
            if slug in industries:
                out.append(
                    CandidateRelationship(
                        relationship=RelationshipType.BELONGS_TO,
                        source_name=entity.canonical_name,
                        target_name=industries[slug],
                        confidence=Confidence.of(0.8),
                        provenance=_DERIVED,
                    )
                )
                break
    return tuple(out)


_DIFFICULTY_ORDER = {"beginner": 0, "basic": 0, "intermediate": 1, "advanced": 2,
                     "expert": 3}


def learning_path(
    career: Node, skills: tuple[Node, ...]
) -> tuple[Node, ...]:
    """Order a career's skills into a learning path.

    Ordering is deterministic: declared difficulty (metadata ``difficulty``)
    first, then name. Skills with unknown difficulty sort between basic and
    advanced rather than being fabricated as easy.
    """
    def sort_key(node: Node) -> tuple[int, str]:
        difficulty = (node.metadata.get("difficulty") or "").lower()
        return (_DIFFICULTY_ORDER.get(difficulty, 1), node.canonical_name)

    return tuple(sorted(skills, key=sort_key))


def summarize(node: Node, related: tuple[Node, ...] = ()) -> str:
    """A deterministic career summary composed from stored fields only."""
    parts = [f"{node.canonical_name} ({node.node_type.value})."]
    if node.description:
        parts.append(node.description)
    if node.aliases:
        parts.append("Also known as: " + ", ".join(node.aliases) + ".")
    if node.semantic_tags:
        parts.append("Key themes: " + ", ".join(node.semantic_tags) + ".")
    if related:
        parts.append(
            "Related: " + ", ".join(r.canonical_name for r in related[:5]) + "."
        )
    return " ".join(parts)
