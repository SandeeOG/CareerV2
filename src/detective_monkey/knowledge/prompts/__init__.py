"""Deterministic, versioned prompt templates for the knowledge platform."""

from .templates import (
    TEMPLATE_VERSION,
    GenerationPrompt,
    PromptSection,
    answer_prompt,
    comparison_prompt,
    enrichment_prompt,
    regional_prompt,
    relationship_prompt,
)

__all__ = [
    "TEMPLATE_VERSION",
    "GenerationPrompt",
    "PromptSection",
    "answer_prompt",
    "comparison_prompt",
    "enrichment_prompt",
    "regional_prompt",
    "relationship_prompt",
]
