"""Knowledge platform data models.

Domain aggregates (Career, Skill, Node, Edge, ...) stay in ``domain/``; this
package adds the platform-level envelopes: raw source records, merged canonical
entities, candidate relationships and dynamic (Layer 2) facts.
"""

from .dynamic import DEFAULT_FACT_TTL, DynamicFact, DynamicFactType
from .entities import CandidateRelationship, CanonicalEntity, entity_node_id
from .layers import KnowledgeLayer
from .records import RawKnowledgeRecord, RawRelationshipHint, SourceMetadata

__all__ = [
    "DEFAULT_FACT_TTL",
    "CandidateRelationship",
    "CanonicalEntity",
    "DynamicFact",
    "DynamicFactType",
    "KnowledgeLayer",
    "RawKnowledgeRecord",
    "RawRelationshipHint",
    "SourceMetadata",
    "entity_node_id",
]
