"""LLM-backed structured generation — generation-time only, always validated.

The LLM expands sparse descriptions and proposes relationships between *known*
entities. Its output is never trusted: descriptions are length/shape-checked,
proposed relationships are parsed strictly, restricted to known entities and
whitelisted relationship types, then pushed through the ValidationPipeline like
any other candidate. A missing/failing provider degrades to the deterministic
heuristics — never to an error.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from ...domain.common.confidence import Confidence
from ...domain.common.provenance import Provenance, SourceType
from ...domain.knowledge_graph.node import Node
from ...domain.knowledge_graph.ontology import RelationshipType
from ..models.entities import CandidateRelationship
from ..normalizers.text import slugify
from ..prompts.templates import GenerationPrompt, enrichment_prompt, relationship_prompt


@runtime_checkable
class LLMPort(Protocol):
    """The provider contract (same shape the Explanation Engine uses)."""

    def generate(self, prompt: GenerationPrompt) -> str: ...


# Relationship types the LLM may propose; anything else is discarded.
_ALLOWED_LLM_RELATIONSHIPS = frozenset({
    RelationshipType.REQUIRES,
    RelationshipType.USES,
    RelationshipType.RELATED_TO,
    RelationshipType.BELONGS_TO,
    RelationshipType.LEADS_TO,
    RelationshipType.ALTERNATIVE_TO,
})

_LLM_PROVENANCE = Provenance(
    SourceType.DERIVED, "llm-generated; validated before storage"
)


def extract_json_array(text: str) -> list | None:
    """Pull the first JSON array out of an LLM reply (which may add prose)."""
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, list) else None
    return None


class StructuredGenerator:
    """Structured, schema-checked LLM generation."""

    def __init__(self, llm: LLMPort | None) -> None:
        self._llm = llm

    @property
    def available(self) -> bool:
        return self._llm is not None

    def propose_description(
        self, node: Node, related: tuple[Node, ...] = ()
    ) -> str | None:
        """A generated description, or None when unavailable/implausible."""
        if self._llm is None:
            return None
        text = self._llm.generate(enrichment_prompt(node, related)).strip()
        # Shape check: a plausible description, not an apology, not JSON.
        if not (30 <= len(text) <= 2000) or text.startswith(("{", "[")):
            return None
        return text

    def propose_relationships(
        self, node: Node, known: tuple[Node, ...]
    ) -> tuple[CandidateRelationship, ...]:
        """Relationship candidates among known entities; strictly parsed."""
        if self._llm is None or not known:
            return ()
        reply = self._llm.generate(relationship_prompt(node, known))
        items = extract_json_array(reply)
        if not items:
            return ()

        known_by_slug = {slugify(n.canonical_name): n.canonical_name for n in known}
        out: list[CandidateRelationship] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            rel_name = str(item.get("relationship", "")).upper()
            target = str(item.get("target", ""))
            try:
                relationship = RelationshipType(rel_name)
            except ValueError:
                continue
            if relationship not in _ALLOWED_LLM_RELATIONSHIPS:
                continue
            canonical_target = known_by_slug.get(slugify(target))
            if canonical_target is None:  # the LLM invented an entity — drop it
                continue
            if slugify(canonical_target) == slugify(node.canonical_name):
                continue
            out.append(
                CandidateRelationship(
                    relationship=relationship,
                    source_name=node.canonical_name,
                    target_name=canonical_target,
                    confidence=Confidence.of(0.5),  # unverified until corroborated
                    provenance=_LLM_PROVENANCE,
                )
            )
        return tuple(out)
