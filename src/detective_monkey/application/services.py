"""Application services (403_SERVICE_ARCHITECTURE.md).

Each service orchestrates one use case: it coordinates repositories, intelligence
engines and the event bus, defines the (logical) transaction boundary, and
publishes domain events after the work persists (403 §4, §12, §17). Services own
no business rules — those live in the engines/domain — and never touch storage
except through repository ports (403 §15).
"""

from __future__ import annotations

from ..contracts import EngineRequest, EngineStatus, IntelligenceContext
from ..domain.recommendation.contracts import RecommendationRequest
from ..domain.recommendation.weights import WeightConfiguration
from ..domain.student.goals import StudentGoals
from ..domain.student.profile import StudentIntelligenceProfile
from ..domain.student.student import Student
from ..domain.common.identifiers import RecommendationId, StudentId
from ..engines.agent.engine import CareerIntelligenceAgent
from ..engines.agent.types import AgentInput
from ..engines.assessment.engine import AssessmentEngine, AssessmentInput
from ..engines.evidence.engine import EvidenceEngine, EvidenceInput
from ..engines.explanation.engine import ExplanationEngine, ExplanationInput
from ..engines.feature_engineering.definitions import FeatureDefinition
from ..engines.feature_engineering.engine import (
    FeatureEngineeringEngine,
    FeatureEngineeringInput,
)
from ..engines.student_intelligence.config import ReasoningConfig
from ..engines.student_intelligence.engine import (
    StudentIntelligenceEngine,
    StudentIntelligenceInput,
)
from .dto import (
    AgentReplyDTO,
    ErrorCode,
    EvidenceSummaryDTO,
    ExplanationDTO,
    ProfileDTO,
    RecommendationDTO,
    RecommendationListDTO,
    ServiceResult,
)
from .ports import (
    CareerCatalogRepository,
    EventPublisher,
    EvidenceGraphRepository,
    ProfileRepository,
    RecommendationRepository,
    StudentRepository,
)


def _ctx(student_id: str | None = None) -> IntelligenceContext:
    return IntelligenceContext(student_id=student_id)


class SubmitAssessmentService:
    """Use case: turn an assessment submission into a persisted Evidence Graph."""

    def __init__(
        self,
        students: StudentRepository,
        evidence_graphs: EvidenceGraphRepository,
        assessment_engine: AssessmentEngine,
        evidence_engine: EvidenceEngine,
        publisher: EventPublisher,
    ) -> None:
        self._students = students
        self._evidence_graphs = evidence_graphs
        self._assessment = assessment_engine
        self._evidence = evidence_engine
        self._publisher = publisher

    def execute(self, payload: AssessmentInput) -> ServiceResult[EvidenceSummaryDTO]:
        student_id = payload.submission.student_id
        ctx = _ctx(student_id.value)

        if not self._students.exists(student_id):
            self._students.add(Student(id=student_id))

        a_resp = self._assessment.execute(EngineRequest(ctx, payload))
        if not a_resp.ok or a_resp.result is None:
            return ServiceResult.fail(
                ErrorCode.VALIDATION_ERROR,
                a_resp.errors[0].message if a_resp.errors else "Assessment failed.",
            )

        e_resp = self._evidence.execute(EngineRequest(
            ctx, EvidenceInput(student_id, existing_evidence=a_resp.result.evidence)))
        if not e_resp.ok or e_resp.result is None:
            return ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "Evidence build failed.")

        graph = e_resp.result
        # Persist, then publish events (405 §10: after successful transaction).
        self._evidence_graphs.save(student_id, graph)
        self._publisher.publish_all(a_resp.events)
        self._publisher.publish_all(e_resp.events)

        quality = a_resp.result.quality
        dto = EvidenceSummaryDTO(
            student_id=student_id.value,
            evidence_count=len(graph.evidence),
            conflicts=len(graph.conflicts),
            completion=quality.completion if quality else None,
        )
        return ServiceResult.ok(dto, warnings=tuple(a_resp.warnings))


class GenerateProfileService:
    """Use case: build and persist a Student Intelligence Profile."""

    def __init__(
        self,
        evidence_graphs: EvidenceGraphRepository,
        profiles: ProfileRepository,
        feature_engine: FeatureEngineeringEngine,
        intelligence_engine: StudentIntelligenceEngine,
        publisher: EventPublisher,
    ) -> None:
        self._evidence_graphs = evidence_graphs
        self._profiles = profiles
        self._features = feature_engine
        self._intelligence = intelligence_engine
        self._publisher = publisher

    def execute(
        self,
        student_id: StudentId,
        feature_definitions: tuple[FeatureDefinition, ...],
        reasoning_config: ReasoningConfig,
    ) -> ServiceResult[ProfileDTO]:
        ctx = _ctx(student_id.value)
        graph = self._evidence_graphs.get(student_id)
        if graph is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence for student.")

        f_resp = self._features.execute(EngineRequest(
            ctx, FeatureEngineeringInput(graph, feature_definitions)))
        if not f_resp.ok or f_resp.result is None:
            return ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "Feature build failed.")

        # New profile version = previous active version + 1.
        active = self._profiles.get_active(student_id)
        next_version = active.profile_version.next() if active else None
        si_input = StudentIntelligenceInput(
            student_id, graph, f_resp.result, reasoning_config,
            profile_version=next_version or _first_version(),
        )
        si_resp = self._intelligence.execute(EngineRequest(ctx, si_input))
        if not si_resp.ok or si_resp.result is None:
            return ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "Profile build failed.")

        profile = si_resp.result
        self._profiles.save(profile)
        self._publisher.publish_all(si_resp.events)
        return ServiceResult.ok(_profile_dto(profile),
                                warnings=tuple(si_resp.warnings))


class GenerateRecommendationsService:
    """Use case: generate and persist ranked recommendations."""

    def __init__(
        self,
        profiles: ProfileRepository,
        careers: CareerCatalogRepository,
        recommendations: RecommendationRepository,
        recommendation_engine,
        publisher: EventPublisher,
    ) -> None:
        self._profiles = profiles
        self._careers = careers
        self._recommendations = recommendations
        self._engine = recommendation_engine
        self._publisher = publisher

    def execute(
        self,
        student_id: StudentId,
        weights: WeightConfiguration,
        student_skills: tuple = (),
        student_education: tuple = (),
        goals: StudentGoals | None = None,
        candidate_limit: int | None = None,
    ) -> ServiceResult[RecommendationListDTO]:
        ctx = _ctx(student_id.value)
        profile = self._profiles.get_active(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No active profile.")
        careers = self._careers.list_all()
        if not careers:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No careers in catalogue.")

        req = RecommendationRequest(
            profile=profile, careers=careers, weights=weights,
            student_skills=student_skills, student_education=student_education,
            goals=goals, candidate_limit=candidate_limit,
        )
        resp = self._engine.execute(EngineRequest(ctx, req))
        if not resp.ok or resp.result is None:
            return ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "Recommendation failed.")

        for rec in resp.result.recommendations:
            self._recommendations.add(rec)
        self._publisher.publish_all(resp.events)

        dto = RecommendationListDTO(
            student_id=student_id.value,
            recommendations=tuple(
                RecommendationDTO(
                    recommendation_id=r.id.value,
                    career_id=r.career_id.value,
                    overall_score=r.overall_score.value,
                    confidence=r.confidence.value.value,
                    skill_gap_count=len(r.skill_gaps),
                )
                for r in resp.result.recommendations
            ),
        )
        warnings = tuple(w.message for w in resp.result.warnings)
        return ServiceResult.ok(dto, warnings=warnings)


class ExplainRecommendationService:
    """Use case: explain a persisted recommendation."""

    def __init__(
        self,
        recommendations: RecommendationRepository,
        explanation_engine: ExplanationEngine,
        careers: CareerCatalogRepository | None = None,
    ) -> None:
        self._recommendations = recommendations
        self._explanation = explanation_engine
        self._careers = careers

    def execute(self, recommendation_id: RecommendationId
                ) -> ServiceResult[ExplanationDTO]:
        rec = self._recommendations.get(recommendation_id)
        if rec is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Recommendation not found.")
        career_name = ""
        if self._careers is not None:
            career = self._careers.get(rec.career_id)
            career_name = career.identity.canonical_name if career else ""
        resp = self._explanation.execute(EngineRequest(
            _ctx(), ExplanationInput(rec, career_name)))
        if not resp.ok or resp.result is None:
            return ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "Explanation failed.")
        ex = resp.result.explanation
        dto = ExplanationDTO(
            explanation_id=ex.id.value,
            recommendation_id=rec.id.value,
            content=ex.content,
            provider=ex.provider,
            confidence=ex.confidence.value.value if ex.confidence else None,
        )
        return ServiceResult.ok(dto, warnings=tuple(resp.warnings))


class AskAgentService:
    """Use case: a conversational turn with the Career Intelligence Agent."""

    def __init__(self, agent: CareerIntelligenceAgent) -> None:
        self._agent = agent

    def execute(self, payload: AgentInput) -> ServiceResult[AgentReplyDTO]:
        resp = self._agent.execute(EngineRequest(_ctx(), payload))
        if not resp.ok or resp.result is None:
            return ServiceResult.fail(ErrorCode.INTERNAL_ERROR, "Agent failed.")
        r = resp.result
        dto = AgentReplyDTO(
            intent=r.intent.value,
            response=r.response,
            needs_clarification=r.needs_clarification,
            actions=r.platform_actions,
        )
        return ServiceResult.ok(dto, warnings=tuple(resp.warnings))


# -- helpers ---------------------------------------------------------------


def _first_version():
    from ..domain.common.versioning import Version
    return Version(1)


def _profile_dto(profile: StudentIntelligenceProfile) -> ProfileDTO:
    return ProfileDTO(
        profile_id=profile.id.value,
        student_id=profile.student_id.value,
        version=profile.profile_version.number,
        constructs=tuple((c.construct, c.score.value) for c in profile.construct_scores),
        domains=tuple((d.domain, d.score.value) for d in profile.domain_scores),
        completeness=(
            profile.reliability.evidence_completeness.value
            if profile.reliability.evidence_completeness else None
        ),
    )
