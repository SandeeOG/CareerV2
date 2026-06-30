"""Intelligence Evaluation Engine (29_INTELLIGENCE_EVALUATION.md).

Runs the applicable evaluators over whichever platform artifacts are supplied and
assembles a versioned, auditable EvaluationReport. Evaluation is independent of
production engines (§25) and never modifies their outputs (INV-01).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...contracts import (
    BaseEngine,
    EngineMetadata,
    EngineOutcome,
    EngineRequest,
    IntelligenceLayer,
)
from ...domain.common.versioning import Version
from ...domain.recommendation.contracts import RecommendationResponse
from ...domain.student.profile import StudentIntelligenceProfile
from ..evidence.graph import EvidenceGraph
from ..explanation.explanation_object import ExplanationObject
from ..feature_engineering.store import FeatureSet
from ..retrieval.packages import ContextPackage
from . import evaluators as ev
from .metrics import EvaluationReport, MetricGroup

ENGINE_VERSION = Version(1, "P2")


@dataclass(frozen=True, slots=True)
class EvaluationInput:
    """Optional artifacts to evaluate; each present one is measured (29 §3)."""

    evidence_graph: EvidenceGraph | None = None
    feature_set: FeatureSet | None = None
    profile: StudentIntelligenceProfile | None = None
    recommendation_response: RecommendationResponse | None = None
    explanation_object: ExplanationObject | None = None
    context_package: ContextPackage | None = None
    calibration_samples: tuple[tuple[float, bool], ...] = field(default_factory=tuple)


class EvaluationEngine(BaseEngine[EvaluationInput, EvaluationReport]):
    """Read-only, deterministic evaluation across the intelligence stack (29 §1)."""

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="evaluation_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.INFERENCE,
            description="Measures quality across every intelligence layer.",
        )

    def _run(self, request: EngineRequest[EvaluationInput]) -> EngineOutcome[EvaluationReport]:
        p = request.payload
        groups: list[MetricGroup] = []
        if p.evidence_graph is not None:
            groups.append(ev.evaluate_evidence(p.evidence_graph))
        if p.feature_set is not None:
            groups.append(ev.evaluate_features(p.feature_set))
        if p.profile is not None:
            groups.append(ev.evaluate_student_intelligence(p.profile))
        if p.recommendation_response is not None:
            groups.append(ev.evaluate_recommendations(p.recommendation_response))
        if p.explanation_object is not None:
            groups.append(ev.evaluate_explanation(p.explanation_object))
        if p.context_package is not None:
            groups.append(ev.evaluate_retrieval(p.context_package))
        if p.calibration_samples:
            groups.append(ev.evaluate_calibration(list(p.calibration_samples)))

        report = EvaluationReport(groups=tuple(groups))
        return EngineOutcome(
            result=report,
            metrics={"layers_evaluated": str(len(groups))},
        )
