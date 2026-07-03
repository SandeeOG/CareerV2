"""The KnowledgeSource contract and source registry.

Every structured dataset the platform learns from — O*NET, ESCO, government
labour statistics, university databases, future public APIs — implements this
one interface: ``fetch``, ``normalize``, ``validate``, ``metadata``. The rest
of the platform only ever sees `RawKnowledgeRecord`s, so any source can be
added or replaced without touching generation, validation or the graph.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.records import RawKnowledgeRecord, SourceMetadata


class KnowledgeSource(ABC):
    """One replaceable origin of raw knowledge."""

    @abstractmethod
    def metadata(self) -> SourceMetadata:
        """Publish who this source is and how reliable it is."""

    @abstractmethod
    def fetch(self) -> tuple[RawKnowledgeRecord, ...]:
        """Retrieve raw records from the underlying dataset/API."""

    def normalize(
        self, records: tuple[RawKnowledgeRecord, ...]
    ) -> tuple[RawKnowledgeRecord, ...]:
        """Source-local cleanup: trim whitespace, drop empty aliases.

        Cross-source canonicalization (merging "Programmer" into "Software
        Engineer") happens later in ``normalizers``; this stage only makes each
        record internally tidy.
        """
        out = []
        for r in records:
            out.append(
                RawKnowledgeRecord(
                    source_id=r.source_id,
                    entity_type=r.entity_type,
                    name=" ".join(r.name.split()),
                    description=r.description.strip(),
                    aliases=tuple(
                        " ".join(a.split()) for a in r.aliases if a.strip()
                    ),
                    tags=tuple(t.strip().lower() for t in r.tags if t.strip()),
                    attributes=r.attributes,
                    relationships=r.relationships,
                    external_code=r.external_code.strip(),
                )
            )
        return tuple(out)

    def validate(
        self, records: tuple[RawKnowledgeRecord, ...]
    ) -> tuple[RawKnowledgeRecord, ...]:
        """Drop structurally unusable rows; keep the rest.

        This is the *source-level* gate (malformed rows). The platform-level
        `ValidationPipeline` still judges the merged canonical entities.
        """
        kept = []
        seen: set[tuple[str, str]] = set()
        for r in records:
            if not r.name.strip():
                continue
            key = (r.entity_type.value, r.name.lower())
            if key in seen:  # a source must not assert the same entity twice
                continue
            seen.add(key)
            kept.append(r)
        return tuple(kept)


class SourceRegistry:
    """The set of sources the platform currently generates knowledge from."""

    def __init__(self) -> None:
        self._sources: dict[str, KnowledgeSource] = {}

    def register(self, source: KnowledgeSource) -> None:
        source_id = source.metadata().source_id
        self._sources[source_id] = source

    def unregister(self, source_id: str) -> None:
        self._sources.pop(source_id, None)

    def get(self, source_id: str) -> KnowledgeSource | None:
        return self._sources.get(source_id)

    def list_all(self) -> tuple[KnowledgeSource, ...]:
        return tuple(self._sources[k] for k in sorted(self._sources))
