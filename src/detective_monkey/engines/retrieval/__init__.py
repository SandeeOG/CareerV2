"""Knowledge Retrieval Engine (27_KNOWLEDGE_RETRIEVAL_ARCHITECTURE.md)."""

from .engine import KnowledgeRetrievalEngine, RetrievalInput
from .intent import Intent, classify
from .packages import (
    ContextPackage,
    RetrievalPromptPackage,
    RetrievedItem,
    SourceKind,
    VectorHit,
    VectorIndex,
)

__all__ = [
    "KnowledgeRetrievalEngine",
    "RetrievalInput",
    "Intent",
    "classify",
    "ContextPackage",
    "RetrievedItem",
    "SourceKind",
    "RetrievalPromptPackage",
    "VectorIndex",
    "VectorHit",
]
