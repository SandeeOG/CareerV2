"""Deterministic evaluators (29_INTELLIGENCE_EVALUATION.md §5–§12).

Each evaluator reads a platform artifact and produces a `MetricGroup`. They are
pure and read-only — evaluation never changes production behaviour (INV-01).
"""

from __future__ import annotations

from ...domain.recommendation.contracts import RecommendationResponse
from ...domain.student.profile import StudentIntelligenceProfile
from ..evidence.graph import EvidenceGraph
from ..explanation.explanation_object import ExplanationObject
from ..feature_engineering.store import FeatureSet
from ..retrieval.packages import ContextPackage, SourceKind
from .metrics import Metric, MetricGroup


def evaluate_evidence(graph: EvidenceGraph) -> MetricGroup:
    """Evidence quality (29 §5)."""
    n = len(graph.evidence)
    mean_conf = (
        sum(e.confidence.value.value for e in graph.evidence) / n if n else 0.0
    )
    conflict_rate = (len(graph.conflicts) / len(graph.subjects())) if graph.subjects() else 0.0
    verified = sum(1 for e in graph.evidence if e.metadata.get("verified") == "true")
    return MetricGroup("evidence", (
        Metric("coverage", float(n), detail="evidence count"),
        Metric("mean_confidence", mean_conf),
        Metric("conflict_rate", conflict_rate),
        Metric("verification_rate", (verified / n) if n else 0.0),
    ))


def evaluate_features(feature_set: FeatureSet) -> MetricGroup:
    """Feature quality (29 §6)."""
    feats = feature_set.features
    n = len(feats)
    mean_conf = sum(f.confidence.value.value for f in feats) / n if n else 0.0
    mean_compl = sum(f.completeness for f in feats) / n if n else 0.0
    missing = sum(1 for f in feats if f.completeness < 1.0)
    return MetricGroup("features", (
        Metric("coverage", float(n)),
        Metric("mean_confidence", mean_conf),
        Metric("mean_completeness", mean_compl),
        Metric("missing_ratio", (missing / n) if n else 0.0),
    ))


def evaluate_student_intelligence(profile: StudentIntelligenceProfile) -> MetricGroup:
    """Profile quality / calibration inputs (29 §7)."""
    cs = profile.construct_scores
    mean_conf = sum(c.confidence.value.value for c in cs) / len(cs) if cs else 0.0
    rel = profile.reliability
    return MetricGroup("student_intelligence", (
        Metric("construct_coverage", float(len(cs))),
        Metric("mean_construct_confidence", mean_conf),
        Metric("evidence_completeness",
               rel.evidence_completeness.value if rel.evidence_completeness else 0.0),
        Metric("internal_consistency",
               rel.internal_consistency.value if rel.internal_consistency else 0.0),
    ))


def evaluate_recommendations(response: RecommendationResponse) -> MetricGroup:
    """Recommendation quality (29 §8). Offline + structural metrics."""
    recs = response.recommendations
    n = len(recs)
    mean_score = sum(r.overall_score.value for r in recs) / n if n else 0.0
    mean_conf = sum(r.confidence.value.value for r in recs) / n if n else 0.0
    evidence_rate = sum(1 for r in recs if r.evidence) / n if n else 0.0
    # Diversity: variety of leading dimension across the list.
    leading = {
        max(r.dimension_scores, key=lambda d: d.score.value).dimension
        for r in recs
        if r.dimension_scores
    }
    diversity = (len(leading) / n) if n else 0.0
    return MetricGroup("recommendations", (
        Metric("coverage", float(n)),
        Metric("mean_score", mean_score),
        Metric("mean_confidence", mean_conf),
        Metric("evidence_presence_rate", evidence_rate),
        Metric("diversity", diversity),
    ))


def evaluate_explanation(obj: ExplanationObject) -> MetricGroup:
    """Explanation fidelity (29 §9)."""
    has_support = 1.0 if obj.supporting_evidence else 0.0
    # Faithfulness proxy: supported, uncertainty surfaced when confidence is low,
    # and actionable improvements present when there are gaps.
    low_conf = obj.confidence.value.value < 0.5
    uncertainty_ok = 1.0 if (not low_conf or obj.uncertainty) else 0.0
    actionable = 1.0 if (not obj.skill_gaps or obj.suggested_improvements) else 0.0
    faithfulness = (has_support + uncertainty_ok + actionable) / 3.0
    return MetricGroup("explanation", (
        Metric("evidence_coverage", has_support),
        Metric("uncertainty_communicated", uncertainty_ok),
        Metric("actionability", actionable),
        Metric("faithfulness", faithfulness),
    ))


def evaluate_retrieval(context: ContextPackage) -> MetricGroup:
    """Retrieval effectiveness (29 §10). Graph retrieval should lead."""
    items = context.items
    n = len(items)
    mean_rel = sum(i.relevance for i in items) / n if n else 0.0
    graph_items = sum(
        1 for i in items
        if i.kind in (SourceKind.KNOWLEDGE, SourceKind.DECISION, SourceKind.EVIDENCE)
    )
    vector_items = sum(1 for i in items if i.kind is SourceKind.VECTOR)
    graph_ratio = (graph_items / n) if n else 0.0
    return MetricGroup("retrieval", (
        Metric("items", float(n)),
        Metric("mean_relevance", mean_rel),
        Metric("graph_ratio", graph_ratio,
               detail="share of canonical-graph items vs vector (should dominate)"),
        Metric("vector_items", float(vector_items)),
    ))


def evaluate_calibration(samples: list[tuple[float, bool]], bins: int = 5) -> MetricGroup:
    """Confidence calibration over (confidence, hit) samples (29 §12).

    Expected Calibration Error: mean |bucket mean-confidence − bucket hit-rate|.
    """
    if not samples:
        return MetricGroup("calibration", (Metric("samples", 0.0),))
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for conf, hit in samples:
        idx = min(bins - 1, int(conf * bins))
        buckets[idx].append((conf, hit))
    ece = 0.0
    total = len(samples)
    for bucket in buckets:
        if not bucket:
            continue
        mean_conf = sum(c for c, _ in bucket) / len(bucket)
        hit_rate = sum(1 for _, h in bucket if h) / len(bucket)
        ece += (len(bucket) / total) * abs(mean_conf - hit_rate)
    return MetricGroup("calibration", (
        Metric("samples", float(total)),
        Metric("expected_calibration_error", ece),
    ))
