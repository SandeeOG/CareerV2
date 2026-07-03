"""AI feature extraction from open-ended responses — provider-agnostic.

The engine talks only to the application's LLM port (any object with
``generate(prompt) -> str``): Gemini, Claude, OpenAI, DeepSeek, Ollama or the
offline template provider all plug in behind the same contract. No provider is
ever named here.

The AI's single responsibility is structured feature extraction: read the open
responses, return strict JSON following the canonical schema. It never
recommends, scores or ranks careers. Every response is validated (valid JSON,
known features, scores/confidence in [0,1], evidence present); invalid output
is retried and never stored. When no provider is available (or every attempt
fails validation) a deterministic keyword extractor supplies the features, so
the pipeline always completes offline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .schema import FEATURE_NAMES, ExtractedFeature, OpenResponse

MAX_ATTEMPTS = 2  # initial call + one retry on validation failure


# -- prompt package (structurally compatible with every LLM provider) --------


@dataclass(frozen=True, slots=True)
class PromptSection:
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class ExtractionPrompt:
    """Deterministically-assembled prompt. Matches the platform-wide
    ``_PromptLike`` shape (system_prompt / sections / user_question), so any
    registered provider can serve it."""

    system_prompt: str
    sections: tuple[PromptSection, ...]
    user_question: str


_SYSTEM_PROMPT = (
    "You are a feature-extraction service inside a career-guidance platform. "
    "You read a student's open-ended answers and extract structured features. "
    "You do NOT recommend, score or rank careers. "
    "Respond with a single JSON object and nothing else — no prose, no markdown fences. "
    "Keys must be feature names from the allowed list. Each value is an object "
    'like {"score": 0.8, "confidence": 0.7, "evidence": ["short quote or paraphrase"]}. '
    "score and confidence are numbers between 0 and 1. evidence must contain at "
    "least one short string grounded in the student's own words. Only include "
    "features the answers actually support — omit the rest."
)


def build_extraction_prompt(responses: tuple[OpenResponse, ...]) -> ExtractionPrompt:
    answers = "\n\n".join(
        f"Q: {r.prompt}\nA: {r.text.strip()}" for r in responses if r.text.strip()
    )
    return ExtractionPrompt(
        system_prompt=_SYSTEM_PROMPT,
        sections=(
            PromptSection("Allowed features", ", ".join(FEATURE_NAMES)),
            PromptSection("Student answers", answers),
        ),
        user_question=(
            "Extract the supported features from these answers as strict JSON."
        ),
    )


# -- validation ---------------------------------------------------------------


class ExtractionValidationError(ValueError):
    """The AI response violated the canonical schema."""


def parse_and_validate(text: str) -> dict[str, ExtractedFeature]:
    """Parse an AI response into validated features. Raises on any violation —
    invalid responses are never stored."""
    if not text or not text.strip():
        raise ExtractionValidationError("Empty response.")
    # Tolerate markdown fences / surrounding prose: take the outermost object.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ExtractionValidationError("No JSON object found.")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ExtractionValidationError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise ExtractionValidationError("Response must be a non-empty JSON object.")

    features: dict[str, ExtractedFeature] = {}
    for name, value in data.items():
        if name not in FEATURE_NAMES:
            raise ExtractionValidationError(f"Unknown feature '{name}'.")
        if not isinstance(value, dict):
            raise ExtractionValidationError(f"Feature '{name}' must be an object.")
        score = value.get("score")
        confidence = value.get("confidence")
        evidence = value.get("evidence")
        if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
            raise ExtractionValidationError(f"'{name}.score' must be in [0, 1].")
        if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
            raise ExtractionValidationError(f"'{name}.confidence' must be in [0, 1].")
        if (not isinstance(evidence, list) or not evidence
                or not all(isinstance(e, str) and e.strip() for e in evidence)):
            raise ExtractionValidationError(f"'{name}.evidence' must be a non-empty list of strings.")
        features[name] = ExtractedFeature(
            score=round(float(score), 4),
            confidence=round(float(confidence), 4),
            evidence=tuple(str(e).strip() for e in evidence[:4]),
        )
    return features


def extract_with_ai(llm: object | None, responses: tuple[OpenResponse, ...]
                    ) -> dict[str, ExtractedFeature] | None:
    """Ask the configured provider for features; validate + retry. Returns
    None when no provider is available or every attempt fails validation."""
    answered = tuple(r for r in responses if r.text.strip())
    if llm is None or not hasattr(llm, "generate") or not answered:
        return None
    prompt = build_extraction_prompt(answered)
    for _ in range(MAX_ATTEMPTS):
        try:
            raw = llm.generate(prompt)  # type: ignore[attr-defined]
        except Exception:
            return None  # provider failure is isolated; fall back
        try:
            return parse_and_validate(raw or "")
        except ExtractionValidationError:
            continue  # automatic retry; invalid output is never stored
    return None


# -- deterministic fallback extractor ----------------------------------------
# Keyword heuristics over the student's own words. Much weaker than a real
# model, so confidence is deliberately modest — but the pipeline always
# completes, offline and reproducibly.

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "analytical_thinking": ("logic", "analy", "math", "solve", "puzzle", "reason", "calculat"),
    "creativity": ("creativ", "imagin", "design", "invent", "original", "idea"),
    "leadership": ("lead", "captain", "organis", "organiz", "coordinat", "team lead", "head "),
    "communication": ("speak", "present", "debate", "writ", "explain", "communicat", "language"),
    "problem_solving": ("problem", "solve", "fix", "challeng", "figure out", "solution"),
    "curiosity": ("curio", "why", "wonder", "learn", "discover", "explor", "how things work"),
    "technical_interest": ("code", "coding", "program", "computer", "software", "app", "robot",
                           "tech", "engineer", "machine", "electronics", "ai", "data"),
    "business_interest": ("business", "startup", "sell", "market", "profit", "compan",
                          "entrepreneur", "money", "invest", "trade"),
    "artistic_interest": ("art", "draw", "paint", "music", "sing", "dance", "film", "photo",
                          "design", "write stories", "poetry", "craft"),
    "helping_others": ("help", "volunteer", "teach", "care", "doctor", "nurse", "support",
                       "community", "social work", "charity"),
    "entrepreneurship": ("startup", "start my own", "my own business", "founder", "venture", "entrepreneur"),
    "risk_tolerance": ("risk", "adventur", "dare", "bold", "try new"),
    "teamwork": ("team", "together", "group", "collaborat", "friends and i"),
    "independence": ("alone", "myself", "independent", "on my own", "self-taught"),
    "research_interest": ("research", "experiment", "science", "study", "investigat", "lab"),
    "hands_on_work": ("build", "make", "hands", "craft", "repair", "fix", "sport", "outdoor"),
    "people_interaction": ("people", "talk", "meet", "social", "friend", "interact"),
    "attention_to_detail": ("detail", "careful", "precise", "accurat", "perfection", "neat"),
    "international_interest": ("abroad", "country", "travel", "international", "world", "global"),
}


def heuristic_extraction(responses: tuple[OpenResponse, ...]
                         ) -> dict[str, ExtractedFeature]:
    """Deterministic keyword extraction — the graceful-degradation path."""
    features: dict[str, ExtractedFeature] = {}
    answered = [r for r in responses if r.text.strip()]
    if not answered:
        return features
    corpus = [(r, r.text.lower()) for r in answered]
    for feature, keywords in _KEYWORDS.items():
        if feature not in FEATURE_NAMES or not keywords:
            continue
        hits: list[str] = []
        for response, text in corpus:
            matched = [k for k in keywords if k in text]
            if matched:
                snippet = response.text.strip().replace("\n", " ")
                if len(snippet) > 110:
                    snippet = snippet[:107] + "…"
                hits.append(f"Wrote: “{snippet}”")
        if hits:
            score = min(1.0, 0.55 + 0.15 * len(hits))
            features[feature] = ExtractedFeature(
                score=round(score, 4),
                confidence=round(min(0.6, 0.35 + 0.1 * len(hits)), 4),
                evidence=tuple(dict.fromkeys(hits))[:3],
            )
    return features
