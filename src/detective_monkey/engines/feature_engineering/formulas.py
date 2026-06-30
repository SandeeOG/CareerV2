"""Feature formulas (24_FEATURE_ENGINEERING_ENGINE.md §6, §7, §13).

Formulas are kept external to the engine (INV-06): they are registered callables
keyed by ``formula_id``. The engine resolves and applies them but never embeds
the maths. A small set of deterministic defaults is provided; new formulas are
added by registration, not by editing the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ...domain.common.evidence import Evidence
from ...domain.common.identifiers import EvidenceId
from .definitions import FeatureDefinition


@dataclass(frozen=True, slots=True)
class FormulaContext:
    """Inputs available to a formula for one feature/student."""

    definition: FeatureDefinition
    evidence_by_subject: dict[str, list[Evidence]]
    dependencies: dict[str, "FormulaResult"] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FormulaResult:
    """A formula's deterministic output before normalization."""

    value: float
    confidence: float
    completeness: float
    sources: tuple[EvidenceId, ...] = ()


Formula = Callable[[FormulaContext], FormulaResult]


def _value(ev: Evidence) -> float | None:
    raw = ev.metadata.get("value")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def evidence_mean(ctx: FormulaContext) -> FormulaResult:
    """Confidence-weighted mean of evidence values across the declared inputs."""
    pairs: list[tuple[float, float]] = []
    sources: list[EvidenceId] = []
    found_subjects = 0
    for subject in ctx.definition.inputs:
        items = ctx.evidence_by_subject.get(subject, [])
        subject_has_value = False
        for ev in items:
            v = _value(ev)
            if v is not None:
                c = ev.confidence.value.value
                pairs.append((v, c))
                sources.append(ev.id)
                subject_has_value = True
        if subject_has_value:
            found_subjects += 1
    expected = max(1, len(ctx.definition.inputs))
    completeness = found_subjects / expected
    if not pairs:
        return FormulaResult(0.0, 0.0, completeness, ())
    total_c = sum(c for _, c in pairs)
    value = sum(v * c for v, c in pairs) / total_c if total_c else (
        sum(v for v, _ in pairs) / len(pairs)
    )
    confidence = (total_c / len(pairs)) * completeness
    return FormulaResult(value, confidence, completeness, tuple(sources))


def presence(ctx: FormulaContext) -> FormulaResult:
    """1.0 if any evidence exists for the inputs, else 0.0."""
    sources: list[EvidenceId] = []
    for subject in ctx.definition.inputs:
        for ev in ctx.evidence_by_subject.get(subject, []):
            sources.append(ev.id)
    present = bool(sources)
    return FormulaResult(1.0 if present else 0.0, 1.0 if present else 0.5,
                         1.0, tuple(sources))


def weighted_sum(ctx: FormulaContext) -> FormulaResult:
    """Weighted combination of dependency features (24 §13 composite features)."""
    deps = ctx.definition.dependencies
    if not deps:
        return FormulaResult(0.0, 0.0, 0.0, ())
    weights = ctx.definition.weights or tuple(1.0 for _ in deps)
    if len(weights) != len(deps):
        raise ValueError(
            f"Feature '{ctx.definition.id}': weights length must match dependencies"
        )
    total_w = sum(weights)
    value = 0.0
    confidences: list[float] = []
    completenesses: list[float] = []
    sources: list[EvidenceId] = []
    for dep_id, w in zip(deps, weights):
        dep = ctx.dependencies.get(dep_id)
        if dep is None:
            continue
        value += dep.value * (w / total_w)
        confidences.append(dep.confidence)
        completenesses.append(dep.completeness)
        sources.extend(dep.sources)
    confidence = min(confidences) if confidences else 0.0
    completeness = (sum(completenesses) / len(completenesses)) if completenesses else 0.0
    return FormulaResult(value, confidence, completeness, tuple(sources))


class FormulaRegistry:
    """Registry mapping formula ids to callables (24 §28 'store as metadata')."""

    def __init__(self) -> None:
        self._formulas: dict[str, Formula] = {}

    def register(self, formula_id: str, formula: Formula) -> None:
        self._formulas[formula_id] = formula

    def get(self, formula_id: str) -> Formula | None:
        return self._formulas.get(formula_id)

    def has(self, formula_id: str) -> bool:
        return formula_id in self._formulas


def default_registry() -> FormulaRegistry:
    reg = FormulaRegistry()
    reg.register("evidence_mean", evidence_mean)
    reg.register("presence", presence)
    reg.register("weighted_sum", weighted_sum)
    return reg
