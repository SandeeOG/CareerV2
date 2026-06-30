"""Provider adapters (409_PROVIDER_ARCHITECTURE.md).

Provider-agnostic adapters for external capabilities. The platform depends on
provider *contracts*, never implementations (409 INV-01/02). These dependency-
free defaults let the AI-facing engines run end-to-end without any real provider;
swapping in Anthropic/OpenAI/Qdrant later is a pure adapter change.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, runtime_checkable

from ..engines.explanation.explanation_object import PromptPackage
from ..engines.retrieval.packages import VectorHit


@runtime_checkable
class _PromptLike(Protocol):
    """Structural shape shared by every deterministically-assembled prompt
    package in the platform (``explanation.PromptPackage``,
    ``retrieval.RetrievalPromptPackage``). Providers depend on this shape, not
    on a specific engine's type, so one provider serves every AI engine."""

    system_prompt: str
    sections: tuple
    user_question: str


def _render_prompt_text(prompt: _PromptLike) -> str:
    parts = [prompt.system_prompt, ""]
    for section in prompt.sections:
        parts.append(f"## {section.title}\n{section.content}")
    parts.append(f"\nStudent question: {prompt.user_question}")
    return "\n".join(parts)


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


class GeminiProvider:
    """Google Gemini `LLMPort` adapter (409_PROVIDER_ARCHITECTURE.md §6 AI Providers).

    Provider-specific code lives only here; the rest of the platform depends on
    the `LLMPort`/duck-typed `_PromptLike` contracts, never on Gemini directly
    (409 INV-01/02). Uses the Gemini REST API via ``httpx`` (lazy import — the
    core stays dependency-free; install the ``api`` extra to use this).

    Failures never raise: a structured-error/timeout/network problem returns an
    empty string so the calling engine falls back to its deterministic template
    (18 §15 graceful degradation, 409 INV-04 "provider failures remain isolated").
    """

    _ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 20.0,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiProvider requires a non-empty api_key")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def generate(self, prompt: _PromptLike) -> str:
        try:
            import httpx
        except ImportError:
            return ""  # optional dependency not installed; caller falls back

        try:
            response = httpx.post(
                self._ENDPOINT.format(model=self._model),
                params={"key": self._api_key},
                json={
                    "contents": [
                        {"role": "user", "parts": [{"text": _render_prompt_text(prompt)}]}
                    ],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 700},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts)
            return text.strip()
        except Exception:
            # Network error, bad key, rate limit, malformed response, ... — never
            # crash the engine. The caller treats an empty string as "unavailable".
            return ""


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
