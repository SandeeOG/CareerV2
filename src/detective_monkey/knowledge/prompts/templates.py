"""Deterministic prompt templates for knowledge generation and reasoning.

Prompts are assembled deterministically from retrieved/validated inputs — the
LLM is never handed a free-form question about the world. Every template pins
a version so generations are reproducible, and every system prompt carries the
platform's grounding rule: explain and reason over the supplied facts, never
invent salaries, universities, certifications, visa rules or statistics.

`GenerationPrompt` matches the structural `_PromptLike` shape the platform's
LLM providers accept (``system_prompt`` / ``sections`` / ``user_question``),
so any configured provider serves the knowledge platform unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.knowledge_graph.node import Node
from ..models.dynamic import DynamicFact

TEMPLATE_VERSION = "knowledge-prompts-v1"

_GROUNDING = (
    "You are the knowledge engine of Detective Monkey, an AI career platform. "
    "Use ONLY the facts provided in the sections below. Never invent salaries, "
    "universities, certifications, visa rules or labour statistics. If the "
    "provided facts are insufficient, say so explicitly."
)


@dataclass(frozen=True, slots=True)
class PromptSection:
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class GenerationPrompt:
    """A deterministically-assembled, versioned prompt package."""

    system_prompt: str
    sections: tuple[PromptSection, ...]
    user_question: str
    template_version: str = TEMPLATE_VERSION


def _facts_section(facts: tuple[DynamicFact, ...]) -> PromptSection:
    lines = [
        f"- [{f.fact_type.value}{' / ' + f.region if f.region else ''}] "
        f"{f.subject}: {f.summary} (source: {f.provenance.source.value})"
        for f in facts
    ]
    return PromptSection("Retrieved dynamic facts", "\n".join(lines) or "(none)")


def _nodes_section(title: str, nodes: tuple[Node, ...]) -> PromptSection:
    lines = [
        f"- {n.canonical_name} [{n.node_type.value}]: "
        f"{n.description or '(no description)'}"
        for n in nodes
    ]
    return PromptSection(title, "\n".join(lines) or "(none)")


def enrichment_prompt(node: Node, related: tuple[Node, ...]) -> GenerationPrompt:
    """Ask the LLM to expand a sparse entity description (generation-time only)."""
    return GenerationPrompt(
        system_prompt=_GROUNDING
        + " Write a factual 2-4 sentence description of the given concept for "
          "a student audience. Return plain text only.",
        sections=(
            PromptSection(
                "Concept",
                f"{node.canonical_name} [{node.node_type.value}] — aliases: "
                f"{', '.join(node.aliases) or '(none)'}; tags: "
                f"{', '.join(node.semantic_tags) or '(none)'}",
            ),
            _nodes_section("Related canonical concepts", related),
        ),
        user_question=f"Describe {node.canonical_name}.",
    )


def relationship_prompt(node: Node, candidates: tuple[Node, ...]) -> GenerationPrompt:
    """Ask the LLM to propose relationships among *known* entities only.

    The output format is a JSON array of {"relationship", "target"} objects;
    anything referencing an unknown entity is rejected by validation.
    """
    return GenerationPrompt(
        system_prompt=_GROUNDING
        + ' Propose relationships as a JSON array of objects with keys '
          '"relationship" (one of REQUIRES, USES, RELATED_TO, BELONGS_TO, '
          'LEADS_TO, ALTERNATIVE_TO) and "target" (the exact name of one of '
          "the listed known concepts). Return JSON only.",
        sections=(
            _nodes_section("Subject concept", (node,)),
            _nodes_section("Known concepts you may link to", candidates),
        ),
        user_question=f"Which known concepts relate to {node.canonical_name}, and how?",
    )


def regional_prompt(
    career: Node, location: str, facts: tuple[DynamicFact, ...]
) -> GenerationPrompt:
    """Regional advice: generated from retrieved facts, cached — never stored."""
    return GenerationPrompt(
        system_prompt=_GROUNDING
        + " Give practical regional career advice: nearby opportunity hubs, "
          "whether relocation is typically expected, and learning opportunities "
          "— strictly grounded in the retrieved facts.",
        sections=(
            _nodes_section("Career", (career,)),
            PromptSection("Student location", location),
            _facts_section(facts),
        ),
        user_question=(
            f"What should a student in {location} know about pursuing a career "
            f"as {career.canonical_name}?"
        ),
    )


def comparison_prompt(
    subjects: tuple[Node, ...],
    facts: tuple[DynamicFact, ...],
    student_context: str = "",
) -> GenerationPrompt:
    sections = [
        _nodes_section("Options being compared", subjects),
        _facts_section(facts),
    ]
    if student_context:
        sections.append(PromptSection("Student context", student_context))
    names = ", ".join(n.canonical_name for n in subjects)
    return GenerationPrompt(
        system_prompt=_GROUNDING
        + " Compare the options criterion by criterion using only the retrieved "
          "facts, then give a balanced, personalized conclusion.",
        sections=tuple(sections),
        user_question=f"Compare: {names}.",
    )


def answer_prompt(
    query: str,
    nodes: tuple[Node, ...],
    facts: tuple[DynamicFact, ...],
    student_context: str = "",
) -> GenerationPrompt:
    """The final reasoning step of the retrieval pipeline."""
    sections = [
        _nodes_section("Retrieved canonical knowledge", nodes),
        _facts_section(facts),
    ]
    if student_context:
        sections.append(PromptSection("Student context", student_context))
    return GenerationPrompt(
        system_prompt=_GROUNDING
        + " Answer the student's question using the retrieved knowledge, and "
          "suggest one concrete next step.",
        sections=tuple(sections),
        user_question=query,
    )
