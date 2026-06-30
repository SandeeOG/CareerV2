"""Memory Architecture (19_MEMORY_ARCHITECTURE.md).

Personal, persistent memory that turns Detective Monkey from a stateless app
into a lifelong companion — without ever altering deterministic intelligence.
Semantic memory lives in the Knowledge Graph; working memory is never persisted.
"""

from .memory import Memory, MemoryType, PrivacyLevel

__all__ = ["Memory", "MemoryType", "PrivacyLevel"]
