"""Individual validation checks.

AI-generated and source-imported knowledge is untrusted until it passes these
checks: missing fields, schema correctness, confidence thresholds, duplicate
entities, cross-source attribute conflicts and invalid relationships. Each
check is a pure function returning issues; the pipeline decides acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ...domain.knowledge_graph.ontology import NodeType, RelationshipType
from ..models.entities import CandidateRelationship, CanonicalEntity
from ..models.records import RawKnowledgeRecord
from ..normalizers.text import slugify


class Severity(str, Enum):
    ERROR = "error"  # the item is rejected
    WARNING = "warning"  # the item is accepted, but flagged


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    subject: str  # entity/relationship the issue concerns


def check_required_fields(entity: CanonicalEntity) -> tuple[ValidationIssue, ...]:
    issues = []
    if not entity.description:
        issues.append(
            ValidationIssue(
                Severity.WARNING, "missing_description",
                "entity has no description; enrichment should fill it",
                entity.canonical_name,
            )
        )
    if entity.provenance is None:
        issues.append(
            ValidationIssue(
                Severity.ERROR, "missing_provenance",
                "nothing may be untraceable: entity has no provenance",
                entity.canonical_name,
            )
        )
    return tuple(issues)


def check_schema(entity: CanonicalEntity) -> tuple[ValidationIssue, ...]:
    issues = []
    if entity.slug != slugify(entity.canonical_name):
        issues.append(
            ValidationIssue(
                Severity.ERROR, "slug_mismatch",
                f"slug {entity.slug!r} does not match canonical name",
                entity.canonical_name,
            )
        )
    if entity.canonical_name in entity.aliases:
        issues.append(
            ValidationIssue(
                Severity.ERROR, "self_alias",
                "canonical name must not appear in its own aliases",
                entity.canonical_name,
            )
        )
    if len(entity.description) > 5000:
        issues.append(
            ValidationIssue(
                Severity.ERROR, "description_too_long",
                "description exceeds 5000 characters",
                entity.canonical_name,
            )
        )
    return tuple(issues)


def check_confidence(
    entity: CanonicalEntity, minimum: float
) -> tuple[ValidationIssue, ...]:
    if entity.confidence is None:
        return (
            ValidationIssue(
                Severity.ERROR, "missing_confidence",
                "confidence without evidence is not trustworthy — and no "
                "confidence at all is worse",
                entity.canonical_name,
            ),
        )
    if entity.confidence.value.value < minimum:
        return (
            ValidationIssue(
                Severity.ERROR, "low_confidence",
                f"confidence {entity.confidence.value.value:.2f} below "
                f"threshold {minimum:.2f}",
                entity.canonical_name,
            ),
        )
    return ()


def check_duplicates(
    entities: tuple[CanonicalEntity, ...],
) -> tuple[ValidationIssue, ...]:
    seen: dict[tuple[NodeType, str], str] = {}
    issues = []
    for entity in entities:
        key = (entity.entity_type, entity.slug)
        if key in seen:
            issues.append(
                ValidationIssue(
                    Severity.ERROR, "duplicate_entity",
                    f"duplicate of {seen[key]!r} — normalization must merge these",
                    entity.canonical_name,
                )
            )
        else:
            seen[key] = entity.canonical_name
    return tuple(issues)


def check_conflicts(
    canonical_name: str, group: tuple[RawKnowledgeRecord, ...]
) -> tuple[ValidationIssue, ...]:
    """Flag attribute keys where sources disagree (kept, but flagged)."""
    values: dict[str, set[str]] = {}
    for record in group:
        for k, v in record.attributes.items:
            values.setdefault(k, set()).add(v)
    return tuple(
        ValidationIssue(
            Severity.WARNING, "conflicting_attribute",
            f"sources disagree on {key!r}: {sorted(vals)}",
            canonical_name,
        )
        for key, vals in sorted(values.items())
        if len(vals) > 1
    )


# Relationship types whose endpoints have a fixed semantic direction. Anything
# not listed is permitted between any node types (the ontology stays open).
_ENDPOINT_RULES: dict[RelationshipType, tuple[frozenset[NodeType], frozenset[NodeType]]] = {
    RelationshipType.LOCATED_IN: (
        frozenset(NodeType),
        frozenset({NodeType.COUNTRY, NodeType.REGION}),
    ),
    RelationshipType.CERTIFIED_BY: (
        frozenset(NodeType),
        frozenset({NodeType.INSTITUTION, NodeType.PROFESSIONAL_ASSOCIATION,
                   NodeType.COMPANY}),
    ),
}


def check_relationship(
    relationship: CandidateRelationship,
    known: dict[str, NodeType],
) -> tuple[ValidationIssue, ...]:
    """Validate a candidate against the known canonical entities.

    ``known`` maps canonical-name slug -> entity type.
    """
    issues = []
    source_slug = slugify(relationship.source_name)
    target_slug = slugify(relationship.target_name)
    label = f"{relationship.source_name} -{relationship.relationship.value}-> {relationship.target_name}"

    if source_slug == target_slug:
        issues.append(
            ValidationIssue(Severity.ERROR, "self_relationship",
                            "relationships must connect two distinct entities", label)
        )
    for slug, side in ((source_slug, "source"), (target_slug, "target")):
        if slug not in known:
            issues.append(
                ValidationIssue(
                    Severity.ERROR, "unknown_endpoint",
                    f"{side} entity is not canonical knowledge — the platform "
                    "never links to invented entities", label,
                )
            )
    rule = _ENDPOINT_RULES.get(relationship.relationship)
    if rule and source_slug in known and target_slug in known:
        allowed_sources, allowed_targets = rule
        if known[source_slug] not in allowed_sources or known[target_slug] not in allowed_targets:
            issues.append(
                ValidationIssue(
                    Severity.ERROR, "invalid_endpoint_type",
                    f"{relationship.relationship.value} does not connect "
                    f"{known[source_slug].value} to {known[target_slug].value}",
                    label,
                )
            )
    return tuple(issues)
