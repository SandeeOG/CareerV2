"""Canonicalization: many raw names, one canonical entity.

"Software Developer", "Programmer" and "Backend Engineer" must all resolve to
the single canonical "Software Engineer" entity, carried as aliases. Resolution
is deterministic: an explicit alias table first, then exact slug identity, then
a conservative token-similarity match against already-known canonical names.

`EntityMerger` then folds every raw record that resolved to the same canonical
name into one `CanonicalEntity`, merging descriptions, aliases, tags and
attributes, and building confidence from source agreement and reliability
(confidence never increases without additional evidence — each corroborating
source is that evidence).
"""

from __future__ import annotations

from ...domain.common.attributes import Attributes
from ...domain.common.confidence import Confidence, ConfidenceFactor
from ...domain.common.provenance import Provenance, SourceType
from ...domain.common.scores import UnitInterval
from ...domain.common.versioning import Version
from ...domain.knowledge_graph.ontology import NodeType
from ..models.entities import CanonicalEntity, entity_node_id
from ..models.records import RawKnowledgeRecord, SourceMetadata
from .text import jaccard, normalize_name, slugify

# Conservative: only merge names whose token sets overlap this strongly.
_FUZZY_MERGE_THRESHOLD = 0.75

# Seed alias table for well-known career synonym families. Sources and the
# generation service extend it at runtime; nothing else is hardcoded.
_SEED_ALIASES: dict[str, str] = {
    "software developer": "Software Engineer",
    "programmer": "Software Engineer",
    "backend engineer": "Software Engineer",
    "back-end developer": "Software Engineer",
    "coder": "Software Engineer",
    "data analyst professional": "Data Analyst",
    "machine learning engineer": "ML Engineer",
    "web developer": "Frontend Engineer",
    "front-end developer": "Frontend Engineer",
}


class AliasTable:
    """Explicit alias → canonical-name mapping, extensible at runtime."""

    def __init__(self, seed: dict[str, str] | None = None) -> None:
        base = _SEED_ALIASES if seed is None else seed
        self._aliases: dict[str, str] = {slugify(k): v for k, v in base.items()}

    def add(self, alias: str, canonical: str) -> None:
        self._aliases[slugify(alias)] = normalize_name(canonical)

    def resolve(self, name: str) -> str | None:
        return self._aliases.get(slugify(name))


class Canonicalizer:
    """Resolves any raw name to its canonical form."""

    def __init__(self, aliases: AliasTable | None = None) -> None:
        self._aliases = aliases or AliasTable()
        # canonical names seen so far, per entity type: slug -> display name
        self._known: dict[NodeType, dict[str, str]] = {}

    @property
    def aliases(self) -> AliasTable:
        return self._aliases

    def resolve(self, name: str, entity_type: NodeType) -> str:
        """Return the canonical display name for ``name``."""
        clean = normalize_name(name)
        aliased = self._aliases.resolve(clean)
        if aliased is not None:
            clean = aliased
        known = self._known.setdefault(entity_type, {})
        slug = slugify(clean)
        if slug in known:
            return known[slug]
        # Fuzzy: merge into an existing canonical name when token sets overlap
        # strongly ("Engineer, Software" ~ "Software Engineer").
        for existing_slug, display in known.items():
            if jaccard(slug.replace("-", " "), existing_slug.replace("-", " ")) >= _FUZZY_MERGE_THRESHOLD:
                self._aliases.add(clean, display)
                return display
        known[slug] = clean
        return clean


class EntityMerger:
    """Folds raw records with the same canonical identity into one entity."""

    def __init__(self, canonicalizer: Canonicalizer) -> None:
        self._canonicalizer = canonicalizer

    def merge(
        self,
        records: tuple[RawKnowledgeRecord, ...],
        sources: dict[str, SourceMetadata],
    ) -> tuple[CanonicalEntity, ...]:
        groups: dict[tuple[NodeType, str], list[RawKnowledgeRecord]] = {}
        display: dict[tuple[NodeType, str], str] = {}
        for record in records:
            canonical = self._canonicalizer.resolve(record.name, record.entity_type)
            key = (record.entity_type, slugify(canonical))
            groups.setdefault(key, []).append(record)
            display[key] = canonical

        entities = []
        for key, group in sorted(groups.items(), key=lambda kv: kv[0][1]):
            entities.append(self._merge_group(display[key], key[0], group, sources))
        return tuple(entities)

    def _merge_group(
        self,
        canonical_name: str,
        entity_type: NodeType,
        group: list[RawKnowledgeRecord],
        sources: dict[str, SourceMetadata],
    ) -> CanonicalEntity:
        slug = slugify(canonical_name)

        # Longest description wins; every distinct name/alias becomes an alias.
        description = max((r.description for r in group), key=len, default="")
        aliases: list[str] = []
        tags: list[str] = []
        codes: list[str] = []
        attributes = Attributes()
        for record in sorted(group, key=lambda r: (r.source_id, r.name)):
            for alias in (record.name, *record.aliases):
                clean = normalize_name(alias)
                if clean and clean != canonical_name and clean not in aliases:
                    aliases.append(clean)
            for tag in record.tags:
                if tag not in tags:
                    tags.append(tag)
            if record.external_code and record.external_code not in codes:
                codes.append(record.external_code)
            for k, v in record.attributes.items:
                # First writer wins per key here; the validation pipeline
                # separately reports cross-source conflicts (validators.checks).
                if attributes.get(k) is None:
                    attributes = attributes.set(k, v)

        confidence = self._confidence(group, sources)
        source_ids = sorted({r.source_id for r in group})
        provenance = Provenance(
            source=self._provenance_source(source_ids, sources),
            description=f"merged from {len(group)} record(s)",
            references=tuple(source_ids),
        )
        return CanonicalEntity(
            id=entity_node_id(entity_type, slug),
            entity_type=entity_type,
            canonical_name=canonical_name,
            slug=slug,
            version=Version(1, "generated"),
            description=description,
            aliases=tuple(aliases),
            tags=tuple(tags),
            attributes=attributes,
            external_codes=tuple(codes),
            confidence=confidence,
            provenance=provenance,
        )

    @staticmethod
    def _confidence(
        group: list[RawKnowledgeRecord], sources: dict[str, SourceMetadata]
    ) -> Confidence:
        source_ids = {r.source_id for r in group}
        reliabilities = [
            sources[s].reliability.value for s in source_ids if s in sources
        ]
        base = max(reliabilities) if reliabilities else 0.3
        # Each corroborating source is additional evidence (+0.1, capped).
        corroboration = min(0.2, 0.1 * (len(source_ids) - 1))
        value = min(1.0, base + corroboration)
        factors = [
            ConfidenceFactor(
                "source_reliability", UnitInterval(base),
                "highest reliability among contributing sources",
            )
        ]
        if corroboration:
            factors.append(
                ConfidenceFactor(
                    "corroboration", UnitInterval(corroboration),
                    f"confirmed by {len(source_ids)} independent sources",
                )
            )
        return Confidence(UnitInterval(value), tuple(factors))

    @staticmethod
    def _provenance_source(
        source_ids: list[str], sources: dict[str, SourceMetadata]
    ) -> SourceType:
        if len(source_ids) == 1 and source_ids[0] in sources:
            return sources[source_ids[0]].source_type
        return SourceType.DERIVED
