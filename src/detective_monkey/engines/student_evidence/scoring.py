"""Deterministic scoring of structured responses → canonical features.

Pure functions, no AI. Each answered structured question contributes weighted
observations to canonical features; observations aggregate into an
ExtractedFeature whose confidence grows with the number of independent
observations. Evidence strings are human-readable so the profile stays
explainable end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass

from .definitions import (
    LIKERT,
    MULTI_CHOICE,
    OPEN,
    SCENARIO,
    SINGLE_CHOICE,
    EvidenceAssessment,
    EvidenceQuestion,
)
from .schema import FEATURE_NAMES, ExtractedFeature

LIKERT_MIN, LIKERT_MAX = 1.0, 5.0


@dataclass(frozen=True, slots=True)
class StructuredAnswer:
    """One structured answer: a Likert value or selected option id(s)."""

    question_id: str
    value: float | None = None                    # likert
    selected: tuple[str, ...] = ()                # choice kinds


def _likert01(value: float, reverse: bool) -> float:
    v = max(LIKERT_MIN, min(LIKERT_MAX, value))
    if reverse:
        v = LIKERT_MAX + LIKERT_MIN - v
    return (v - LIKERT_MIN) / (LIKERT_MAX - LIKERT_MIN)


def _observations_for(question: EvidenceQuestion, answer: StructuredAnswer
                      ) -> list[tuple[str, float, float, str]]:
    """Return (feature, value01, weight, evidence_text) observations."""
    obs: list[tuple[str, float, float, str]] = []
    if question.kind == LIKERT and answer.value is not None:
        v01 = _likert01(answer.value, question.reverse)
        agreement = "agreed" if v01 >= 0.5 else "disagreed"
        for feature, weight in question.features:
            obs.append((feature, v01, weight,
                        f"{agreement.capitalize()} with: “{question.prompt}”"))
    elif question.kind in (SINGLE_CHOICE, SCENARIO, MULTI_CHOICE) and answer.selected:
        by_id = {o.id: o for o in question.options}
        for oid in answer.selected[: question.max_choices if question.kind == MULTI_CHOICE else 1]:
            option = by_id.get(oid)
            if option is None:
                continue
            for feature, value in option.features:
                obs.append((feature, value, 1.0,
                            f"Chose “{option.label}” for: {question.prompt}"))
    return obs


def score_structured(assessment: EvidenceAssessment,
                     answers: tuple[StructuredAnswer, ...]
                     ) -> dict[str, ExtractedFeature]:
    """Aggregate all structured answers into canonical features."""
    by_question = {q.id: q for q in assessment.questions()}
    collected: dict[str, list[tuple[float, float, str]]] = {}

    for answer in answers:
        question = by_question.get(answer.question_id)
        if question is None or question.kind == OPEN:
            continue
        for feature, value, weight, evidence in _observations_for(question, answer):
            if feature not in FEATURE_NAMES:
                continue  # definitions bug guard: never emit non-canonical features
            collected.setdefault(feature, []).append((value, weight, evidence))

    features: dict[str, ExtractedFeature] = {}
    for name, rows in collected.items():
        total_weight = sum(w for _, w, _ in rows)
        if total_weight <= 0:
            continue
        score = sum(v * w for v, w, _ in rows) / total_weight
        # Confidence grows with independent observations, capped below 1.0
        # because structured self-report is never certain.
        confidence = min(0.9, 0.45 + 0.15 * len(rows))
        # Keep the strongest evidence lines (highest contribution first).
        ranked = sorted(rows, key=lambda r: -(r[0] * r[1]))
        evidence = tuple(dict.fromkeys(text for _, _, text in ranked))[:3]
        features[name] = ExtractedFeature(
            score=round(min(1.0, max(0.0, score)), 4),
            confidence=round(confidence, 4),
            evidence=evidence,
        )
    return features


def answered_structured_count(assessment: EvidenceAssessment,
                              answers: tuple[StructuredAnswer, ...]) -> int:
    valid = {q.id for q in assessment.structured_questions()}
    return sum(
        1 for a in answers
        if a.question_id in valid and (a.value is not None or a.selected)
    )
