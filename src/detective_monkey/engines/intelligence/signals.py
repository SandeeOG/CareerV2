"""Stage 1 — Signal Extraction.

Transforms assessment evidence (and optional conversation/history) into a
normalized :class:`StudentSignals` vector. Pure, deterministic mapping — no LLM.
The construct→signal mapping is a documented table so it is easy to tune and
extend.
"""

from __future__ import annotations

import re

from ..assessment.responses import AssessmentResult
from .models import ConversationContext, StudentSignals

# Direct construct -> signal mapping (assessment constructs measured 0..100).
_CONSTRUCT_TO_SIGNAL = {
    "analytical_thinking": "logical",
    "creativity": "creative",
    "leadership": "leadership",
    "communication": "verbal",
    "curiosity": "learning_speed",
    "conscientiousness": "academic",
}

# Conversation keywords that raise the technical signal (extension point: a real
# NLP/LLM extractor can replace this without changing the contract).
_TECHNICAL_KEYWORDS = (
    "python", "code", "coding", "programming", "software", "data", "ml",
    "machine learning", "ai", "engineering", "algorithm", "statistics",
)

_NEUTRAL = 0.5


def _construct_values(assessment: AssessmentResult) -> dict[str, float]:
    """Read normalized [0,1] construct values from assessment evidence."""
    values: dict[str, float] = {}
    for ev in assessment.evidence:
        if ev.metadata.get("kind") != "construct_observation":
            continue
        raw = ev.metadata.get("value")
        if raw is None:
            continue
        try:
            values[ev.subject] = max(0.0, min(1.0, float(raw) / 100.0))
        except ValueError:
            continue
    return values


def _mean(*vals: float) -> float:
    present = [v for v in vals if v is not None]
    return sum(present) / len(present) if present else _NEUTRAL


def extract_signals(
    assessment: AssessmentResult,
    conversation: ConversationContext | None = None,
) -> StudentSignals:
    """Extract the normalized signal vector (Stage 1)."""
    values = _construct_values(assessment)

    def sig(signal_name: str) -> float:
        # Reverse-lookup: which construct maps to this signal?
        for construct, mapped in _CONSTRUCT_TO_SIGNAL.items():
            if mapped == signal_name and construct in values:
                return values[construct]
        return _NEUTRAL

    logical = sig("logical")
    creative = sig("creative")
    leadership = sig("leadership")
    verbal = sig("verbal")
    learning_speed = sig("learning_speed")
    academic = sig("academic")

    # Technical: derived from logical, boosted by conversation mentions.
    technical = logical * 0.6
    if conversation is not None:
        text = conversation.text()
        if any(re.search(r"\b" + re.escape(k) + r"\b", text) for k in _TECHNICAL_KEYWORDS):
            technical = max(technical, 0.75)

    return StudentSignals(
        academic=academic,
        logical=logical,
        verbal=verbal,
        creative=creative,
        social=_mean(verbal, leadership),
        leadership=leadership,
        technical=max(0.0, min(1.0, technical)),
        learning_speed=learning_speed,
        risk_tolerance=_mean(leadership, creative),
        motivation=_mean(learning_speed, academic),
        confidence=_mean(leadership, verbal),
    )
