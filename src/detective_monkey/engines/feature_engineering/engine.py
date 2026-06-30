"""Feature Engineering Engine (24_FEATURE_ENGINEERING_ENGINE.md).

Transforms validated evidence into reusable, versioned features. Deterministic
(INV-01, INV-07); every feature references evidence and a definition (INV-02,
INV-03); formulas remain external (INV-06); circular dependencies are rejected
(§11). It performs no recommendations and no interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...contracts import (
    BaseEngine,
    EngineError,
    EngineErrorType,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    IntelligenceLayer,
)
from ...domain.common.confidence import Confidence
from ...domain.common.evidence import Evidence
from ...domain.common.versioning import Version
from ..evidence.graph import EvidenceGraph
from .definitions import FeatureDefinition, Normalization
from .formulas import FormulaContext, FormulaRegistry, FormulaResult, default_registry
from .store import FeatureSet, FeatureValue

ENGINE_VERSION = Version(1, "P2")


@dataclass(frozen=True, slots=True)
class FeatureEngineeringInput:
    """Engine payload (24 §21)."""

    evidence_graph: EvidenceGraph
    definitions: tuple[FeatureDefinition, ...] = field(default_factory=tuple)


class FeatureEngineeringEngine(BaseEngine[FeatureEngineeringInput, FeatureSet]):
    """Deterministic feature computation over evidence (24 §1)."""

    def __init__(self, registry: FormulaRegistry | None = None) -> None:
        self._registry = registry or default_registry()

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="feature_engineering_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.INFERENCE,
            description="Transforms evidence into reusable engineered features.",
        )

    def validate(
        self, request: EngineRequest[FeatureEngineeringInput]
    ) -> list[EngineError]:
        defs = request.payload.definitions
        ids = {d.id for d in defs}
        errors: list[EngineError] = []
        for d in defs:
            if not self._registry.has(d.formula_id):
                errors.append(
                    EngineError(
                        EngineErrorType.CONFIGURATION,
                        "unknown_formula",
                        f"Feature '{d.id}' references unregistered formula "
                        f"'{d.formula_id}'.",
                    )
                )
            for dep in d.dependencies:
                if dep not in ids:
                    errors.append(
                        EngineError(
                            EngineErrorType.CONFIGURATION,
                            "missing_dependency",
                            f"Feature '{d.id}' depends on undefined feature '{dep}'.",
                        )
                    )
        if not errors:
            try:
                self._topological_order(defs)
            except ValueError as exc:
                errors.append(
                    EngineError(EngineErrorType.CONFIGURATION, "cyclic_dependency",
                                str(exc))
                )
        return errors

    def _run(
        self, request: EngineRequest[FeatureEngineeringInput]
    ) -> EngineOutcome[FeatureSet]:
        payload = request.payload
        graph = payload.evidence_graph
        evidence_by_subject = self._index_evidence(graph.evidence)

        order = self._topological_order(payload.definitions)
        by_id = {d.id: d for d in payload.definitions}
        results: dict[str, FormulaResult] = {}
        features: list[FeatureValue] = []

        for feature_id in order:
            defn = by_id[feature_id]
            formula = self._registry.get(defn.formula_id)
            assert formula is not None  # validated above
            ctx = FormulaContext(
                definition=defn,
                evidence_by_subject=evidence_by_subject,
                dependencies={d: results[d] for d in defn.dependencies if d in results},
            )
            raw = formula(ctx)
            value = self._normalize(defn, raw.value)
            results[feature_id] = FormulaResult(
                value=value,
                confidence=raw.confidence,
                completeness=raw.completeness,
                sources=raw.sources,
            )
            features.append(
                FeatureValue(
                    feature_id=feature_id,
                    student_id=graph.student_id,
                    value=value,
                    output_type=defn.output_type,
                    confidence=Confidence.of(max(0.0, min(1.0, raw.confidence))),
                    version=defn.version,
                    completeness=max(0.0, min(1.0, raw.completeness)),
                    sources=raw.sources,
                )
            )

        feature_set = FeatureSet(graph.student_id, tuple(features))
        overall = (
            sum(f.confidence.value.value for f in features) / len(features)
            if features
            else 0.0
        )
        return EngineOutcome(
            result=feature_set,
            confidence=Confidence.of(overall),
            metrics={"features": str(len(features))},
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _index_evidence(evidence: tuple[Evidence, ...]) -> dict[str, list[Evidence]]:
        index: dict[str, list[Evidence]] = {}
        for e in evidence:
            index.setdefault(e.subject, []).append(e)
        return index

    @staticmethod
    def _normalize(defn: FeatureDefinition, value: float) -> float:
        n = defn.normalization
        if n is Normalization.NONE:
            return value
        if n is Normalization.CLAMP_UNIT:
            return max(0.0, min(1.0, value))
        if n is Normalization.PERCENT_TO_UNIT:
            return max(0.0, min(1.0, value / 100.0))
        if n is Normalization.MIN_MAX:
            span = defn.norm_max - defn.norm_min
            if span <= 0:
                return 0.0
            return max(0.0, min(1.0, (value - defn.norm_min) / span))
        return value

    @staticmethod
    def _topological_order(defs: tuple[FeatureDefinition, ...]) -> list[str]:
        """Kahn's algorithm; raises on cycles (24 §11 acyclic dependencies)."""
        ids = [d.id for d in defs]
        deps = {d.id: set(d.dependencies) for d in defs}
        order: list[str] = []
        # Deterministic processing order: sort ready nodes by id.
        ready = sorted([i for i in ids if not deps[i]])
        deps = {k: set(v) for k, v in deps.items()}
        while ready:
            node = ready.pop(0)
            order.append(node)
            for other in ids:
                if node in deps[other]:
                    deps[other].discard(node)
                    if not deps[other] and other not in order and other not in ready:
                        ready.append(other)
                        ready.sort()
        if len(order) != len(ids):
            unresolved = [i for i in ids if i not in order]
            raise ValueError(f"Cyclic feature dependencies among: {unresolved}")
        return order
