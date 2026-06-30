"""Retrieval packages and ports (27_KNOWLEDGE_RETRIEVAL_ARCHITECTURE.md §15, §18, §21).

Retrieval produces a structured Context Package grouped by source, then a
deterministically-assembled prompt. Vector search is an optional, provider-
agnostic port that supplements — never overrides — canonical knowledge (INV-05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class SourceKind(str, Enum):
    """Retrieval sources, in priority order (27 §3, §14)."""

    DECISION = "decision"
    KNOWLEDGE = "knowledge"
    EVIDENCE = "evidence"
    MEMORY = "memory"
    VECTOR = "vector"


# Priority weighting for the prompt budget (27 §14): decision first, vector last.
SOURCE_PRIORITY: dict[SourceKind, int] = {
    SourceKind.DECISION: 5,
    SourceKind.KNOWLEDGE: 4,
    SourceKind.EVIDENCE: 3,
    SourceKind.MEMORY: 2,
    SourceKind.VECTOR: 1,
}


@dataclass(frozen=True, slots=True)
class RetrievedItem:
    """A single retrieved, ranked context item (27 §12)."""

    kind: SourceKind
    label: str
    content: str
    relevance: float
    provenance: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.relevance <= 1.0):
            raise ValueError("RetrievedItem.relevance must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class PromptSection:
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class RetrievalPromptPackage:
    """Deterministically-assembled prompt input (27 §13). Versioned."""

    system_prompt: str
    sections: tuple[PromptSection, ...]
    user_question: str
    template_version: str


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """The retrieval output (27 §21)."""

    intent: str
    items: tuple[RetrievedItem, ...] = field(default_factory=tuple)
    prompt: RetrievalPromptPackage | None = None

    def of_kind(self, kind: SourceKind) -> tuple[RetrievedItem, ...]:
        return tuple(i for i in self.items if i.kind is kind)


@dataclass(frozen=True, slots=True)
class VectorHit:
    label: str
    content: str
    similarity: float
    provenance: str = ""


@runtime_checkable
class VectorIndex(Protocol):
    """Optional semantic search port (27 §11, §18). Supplements graphs."""

    def search(self, query: str, k: int) -> list[VectorHit]: ...
