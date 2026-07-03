"""Raw knowledge records — the wire format between sources and the platform.

Every `KnowledgeSource` (O*NET, ESCO, national statistics, future APIs) emits
the same shape: `RawKnowledgeRecord`. Sources are therefore replaceable — the
rest of the platform never sees source-specific structures. Raw records are
*untrusted*: they pass through normalization and validation before any of them
becomes canonical knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.attributes import Attributes
from ...domain.common.provenance import SourceType
from ...domain.common.scores import UnitInterval
from ...domain.knowledge_graph.ontology import NodeType, RelationshipType


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Published metadata of a knowledge source.

    ``reliability`` feeds validation (low-reliability sources need corroboration)
    and conflict resolution (higher reliability wins a disputed attribute).
    """

    source_id: str
    name: str
    source_type: SourceType
    reliability: UnitInterval
    url: str = ""
    license: str = ""
    dataset_version: str = ""

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("SourceMetadata.source_id must be non-empty")


@dataclass(frozen=True, slots=True)
class RawRelationshipHint:
    """A relationship asserted by a source, by *name* (ids do not exist yet)."""

    relationship: RelationshipType
    target_name: str
    target_type: NodeType
    strength: UnitInterval | None = None

    def __post_init__(self) -> None:
        if not self.target_name.strip():
            raise ValueError("RawRelationshipHint.target_name must be non-empty")


@dataclass(frozen=True, slots=True)
class RawKnowledgeRecord:
    """One entity as reported by one source, before canonicalization."""

    source_id: str
    entity_type: NodeType
    name: str
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    attributes: Attributes = field(default_factory=Attributes)
    relationships: tuple[RawRelationshipHint, ...] = field(default_factory=tuple)
    external_code: str = ""

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("RawKnowledgeRecord.source_id must be non-empty")
