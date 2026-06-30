"""Provider adapters (409_PROVIDER_ARCHITECTURE.md).

Provider-agnostic adapters for external capabilities. The platform depends on
provider *contracts*, never implementations (409 INV-01/02). These dependency-
free defaults let the AI-facing engines run end-to-end without any real provider;
swapping in Anthropic/OpenAI/Qdrant later is a pure adapter change.
"""

from __future__ import annotations

import hashlib
import re

from ..engines.explanation.explanation_object import PromptPackage
from ..engines.retrieval.packages import VectorHit


class TemplateLLMProvider:
    """A deterministic `LLMPort` implementation (no external model).

    It renders the deterministically-assembled PromptPackage into text, so the
    Explanation Engine produces grounded output with zero dependencies and full
    reproducibility. A real provider (Anthropic, OpenAI, local) replaces this
    behind the same `generate` contract (409 §6).
    """

    def generate(self, prompt: PromptPackage) -> str:
        lines = [f"{prompt.user_question}", ""]
        for section in prompt.sections:
            lines.append(f"{section.title}:")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines).strip()


class HashingEmbeddingProvider:
    """Deterministic embedding provider (409 §7).

    Produces a fixed-dimension vector from a stable hash of the text. Useful for
    tests and offline runs; a real embedding model replaces it behind the same
    contract.
    """

    def __init__(self, dimensions: int = 16) -> None:
        self._dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple(
            digest[i % len(digest)] / 255.0 for i in range(self._dimensions)
        )


class InMemoryVectorIndex:
    """A simple `VectorIndex` (409 §7, 27 §11) over registered documents.

    Similarity is deterministic token overlap — enough to demonstrate that vector
    expansion *supplements* graph retrieval without overriding it (27 INV-05).
    """

    def __init__(self) -> None:
        self._docs: list[tuple[str, str, str]] = []  # label, content, provenance

    def add(self, label: str, content: str, provenance: str = "") -> None:
        self._docs.append((label, content, provenance))

    def search(self, query: str, k: int) -> list[VectorHit]:
        q = self._tokens(query)
        scored: list[tuple[float, tuple[str, str, str]]] = []
        for doc in self._docs:
            label, content, _ = doc
            d = self._tokens(f"{label} {content}")
            if not d or not q:
                continue
            sim = len(q & d) / len(q | d)
            if sim > 0:
                scored.append((sim, doc))
        scored.sort(key=lambda s: (-s[0], s[1][0]))
        return [
            VectorHit(label=d[0], content=d[1], similarity=sim, provenance=d[2])
            for sim, d in scored[:k]
        ]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))
