"""Explanation — the domain boundary object for the AI layer (10_DOMAIN_MODEL.md §12).

Recommendation answers *what*; Explanation answers *why* (10 §12). LLMs operate
exclusively in this domain (00 §6, 18 §17). An explanation references a
recommendation and **never modifies it** (10 §12, 16 §22).

The domain models only the *shape* of an explanation. Generating the natural
language is the job of the Explanation Engine / AI layer (Phase 2/3), which must
stay provider-agnostic (00 §11) — hence ``provider`` is a free-form label, not a
dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.confidence import Confidence
from ..common.identifiers import ExplanationId, RecommendationId
from ..common.versioning import Version


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Explanation:
    """An immutable, human-readable explanation of a recommendation."""

    id: ExplanationId
    recommendation_id: RecommendationId
    content: str
    explanation_version: Version
    provider: str = ""  # provider-agnostic label, e.g. "anthropic", "template"
    confidence: Confidence | None = None
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Explanation.content must be non-empty")
