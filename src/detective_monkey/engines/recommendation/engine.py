"""Recommendation Engine (25_RECOMMENDATION_ENGINE.md).

The decision orchestration layer. It owns orchestration, candidate generation,
score/confidence aggregation, diversity, ranking and recommendation construction
(§3) — but owns none of the matching algorithms, which are pluggable match
engines (§1). Deterministic and reproducible (INV-06); ranking never modifies
scores (INV-04); recommendations are immutable (INV-05); labour market adjusts
but never dominates (INV-08); no LLMs participate (INV-07).
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
    EngineStatus,
    IntelligenceLayer,
)
from ...domain.common.confidence import Confidence
from ...domain.common.events import DomainEvent, EventName
from ...domain.common.identifiers import RecommendationId
from ...domain.common.scores import Score
from ...domain.common.versioning import Version, VersionSet
from ...domain.recommendation.contracts import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationWarning,
    WarningSeverity,
)
from ...domain.recommendation.dimensions import DimensionScore
from ...domain.recommendation.evidence import RecommendationEvidence
from ...domain.recommendation.recommendation import AlternativeCareer, Recommendation
from ...domain.career.career import Career
from .matchers import MatchContext, MatchEngine, MatchResult, default_matchers

ENGINE_VERSION = Version(1, "P2")
_MMR_LAMBDA = 0.7  # relevance vs diversity trade-off (25 §13)


@dataclass(frozen=True, slots=True)
class _Scored:
    """Internal aggregate for one career before ranking."""

    career: Career
    overall: float
    confidence: float
    dimension_scores: tuple[DimensionScore, ...]
    evidence: tuple[RecommendationEvidence, ...]
    skill_gaps: tuple
    education_gaps: tuple


class RecommendationEngine(BaseEngine[RecommendationRequest, RecommendationResponse]):
    """Deterministic recommendation orchestrator (25 §1)."""

    def __init__(self, matchers: tuple[MatchEngine, ...] | None = None) -> None:
        self._matchers = matchers or default_matchers()

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine_name="recommendation_engine",
            engine_version=ENGINE_VERSION,
            layer=IntelligenceLayer.DECISION,
            description="Orchestrates match engines into ranked recommendations.",
        )

    def validate(
        self, request: EngineRequest[RecommendationRequest]
    ) -> list[EngineError]:
        req = request.payload
        errors: list[EngineError] = []
        if not req.careers:
            errors.append(
                EngineError(EngineErrorType.VALIDATION, "no_candidates",
                            "At least one candidate career is required.")
            )
        if not req.weights.weights:
            errors.append(
                EngineError(EngineErrorType.CONFIGURATION, "no_weights",
                            "A weight configuration is required (25 §16).")
            )
        return errors

    def _run(
        self, request: EngineRequest[RecommendationRequest]
    ) -> EngineOutcome[RecommendationResponse]:
        req = request.payload
        correlation = request.context.correlation_id
        skills_by_id = {s.skill_id.value: s for s in req.student_skills}
        labour_by_career = {s.career_id.value: s for s in req.labour_market}

        warnings: list[str] = []
        response_warnings: list[RecommendationWarning] = []
        scored: list[_Scored] = []

        # --- Candidate generation + matching (25 §4, §5) ------------------
        for career in req.careers:
            ctx = MatchContext(
                profile=req.profile,
                career=career,
                student_skills=skills_by_id,
                student_education=req.student_education,
                goals=req.goals,
                labour=labour_by_career.get(career.id.value),
            )
            results = [r for m in self._matchers if (r := m.match(ctx)) is not None]
            if not results:
                response_warnings.append(
                    RecommendationWarning(
                        "no_match_data",
                        f"No applicable dimensions for '{career.identity.canonical_name}'.",
                        WarningSeverity.MEDIUM,
                    )
                )
                continue
            scored.append(self._aggregate(career, results, req))

        if not scored:
            return EngineOutcome(
                result=RecommendationResponse(warnings=tuple(response_warnings)),
                status=EngineStatus.PARTIAL,
                confidence=Confidence.of(0.0),
                warnings=["No career could be scored from the provided inputs."],
            )

        # --- Ranking (25 §14) then diversity (25 §13) ---------------------
        scored.sort(key=lambda s: (-s.overall, -s.confidence, s.career.id.value))
        ordered = self._diversify(scored)
        if req.candidate_limit is not None:
            ordered = ordered[: req.candidate_limit]

        # --- Recommendation building (25 §15) -----------------------------
        recommendations = self._build(ordered, scored, req)

        overall_conf = (
            sum(s.confidence for s in ordered) / len(ordered) if ordered else 0.0
        )
        events = [
            DomainEvent(EventName.CANDIDATE_GENERATED, str(req.profile.student_id),
                        correlation_id=correlation),
            DomainEvent(EventName.MATCH_COMPLETED, str(req.profile.student_id),
                        correlation_id=correlation),
            DomainEvent(EventName.RANKING_COMPLETED, str(req.profile.student_id),
                        correlation_id=correlation),
            DomainEvent(EventName.RECOMMENDATION_GENERATED, str(req.profile.student_id),
                        correlation_id=correlation),
        ]
        return EngineOutcome(
            result=RecommendationResponse(
                recommendations=tuple(recommendations),
                warnings=tuple(response_warnings),
                events=tuple(events),
            ),
            status=EngineStatus.SUCCESS,
            confidence=Confidence.of(overall_conf),
            events=events,
            warnings=warnings,
            metrics={
                "candidates": str(len(req.careers)),
                "scored": str(len(scored)),
                "returned": str(len(recommendations)),
            },
        )

    # -- aggregation -------------------------------------------------------

    def _aggregate(
        self, career: Career, results: list[MatchResult], req: RecommendationRequest
    ) -> _Scored:
        """Weighted aggregation over the dimensions that produced a score (25 §16)."""
        present_weights: dict = {}
        for r in results:
            w = req.weights.weight_for(r.dimension)
            present_weights[r.dimension] = w.value if w is not None else 0.0
        total_w = sum(present_weights.values())
        # If config gave the present dimensions no weight, fall back to equal.
        if total_w == 0:
            present_weights = {d: 1.0 for d in present_weights}
            total_w = float(len(present_weights))

        overall = 0.0
        dimension_scores: list[DimensionScore] = []
        evidence: list[RecommendationEvidence] = []
        skill_gaps: tuple = ()
        education_gaps: tuple = ()
        for r in results:
            w = present_weights[r.dimension] / total_w
            overall += r.score.value * w
            dimension_scores.append(
                DimensionScore(r.dimension, r.score, r.confidence,
                               tuple(e for ev in r.evidence for e in ev.sources))
            )
            evidence.extend(r.evidence)
            if r.skill_gaps:
                skill_gaps = r.skill_gaps
            if r.education_gaps:
                education_gaps = r.education_gaps

        # Confidence never exceeds the weakest supporting dimension (25 §17).
        confidence = min(r.confidence.value.value for r in results)
        return _Scored(
            career=career,
            overall=overall,
            confidence=confidence,
            dimension_scores=tuple(dimension_scores),
            evidence=tuple(evidence),
            skill_gaps=skill_gaps,
            education_gaps=education_gaps,
        )

    # -- diversity (25 §13) ------------------------------------------------

    def _diversify(self, scored: list[_Scored]) -> list[_Scored]:
        """Greedy MMR re-ordering to avoid homogeneous recommendations."""
        remaining = list(scored)
        selected: list[_Scored] = []
        while remaining:
            best = None
            best_mmr = float("-inf")
            for cand in remaining:
                rel = cand.overall / 100.0
                if not selected:
                    div = 1.0
                else:
                    div = 1.0 - max(
                        self._similarity(cand.career, s.career) for s in selected
                    )
                mmr = _MMR_LAMBDA * rel + (1 - _MMR_LAMBDA) * div
                # Deterministic tie-break by career id.
                key = (mmr, -ord(cand.career.id.value[0]) if cand.career.id.value else 0)
                if mmr > best_mmr or (mmr == best_mmr and best is not None
                                      and cand.career.id.value < best.career.id.value):
                    best_mmr = mmr
                    best = cand
            assert best is not None
            selected.append(best)
            remaining.remove(best)
        return selected

    @staticmethod
    def _similarity(a: Career, b: Career) -> float:
        sa = {cs.skill_id.value for cs in a.skills}
        sb = {cs.skill_id.value for cs in b.skills}
        if not sa or not sb:
            return 0.0
        inter = len(sa & sb)
        union = len(sa | sb)
        return inter / union if union else 0.0

    # -- builder (25 §15) --------------------------------------------------

    def _build(
        self,
        ordered: list[_Scored],
        all_scored: list[_Scored],
        req: RecommendationRequest,
    ) -> list[Recommendation]:
        by_score = sorted(all_scored, key=lambda s: (-s.overall, s.career.id.value))
        recommendations: list[Recommendation] = []
        for s in ordered:
            alternatives = tuple(
                AlternativeCareer(
                    career_id=other.career.id,
                    relation="alternative",
                    score=Score(other.overall),
                )
                for other in by_score
                if other.career.id.value != s.career.id.value
            )[:3]
            input_versions = (
                VersionSet()
                .with_ref("student_profile", req.profile.profile_version)
                .with_ref("career", s.career.version)
                .with_ref("weights", req.weights.version)
                .with_ref("engine", ENGINE_VERSION)
            )
            recommendations.append(
                Recommendation(
                    id=RecommendationId(
                        f"rec_{req.profile.student_id}_{s.career.identity.slug}"
                        f"_p{req.profile.profile_version.number}"
                    ),
                    career_id=s.career.id,
                    overall_score=Score(s.overall),
                    confidence=Confidence.of(s.confidence),
                    recommendation_version=ENGINE_VERSION,
                    input_versions=input_versions,
                    dimension_scores=s.dimension_scores,
                    evidence=s.evidence,
                    skill_gaps=s.skill_gaps,
                    education_gaps=s.education_gaps,
                    alternative_careers=alternatives,
                )
            )
        return recommendations
