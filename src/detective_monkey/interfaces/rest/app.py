"""FastAPI REST application (401_API_ARCHITECTURE.md) + static SPA host.

Thin controllers: each endpoint validates input, invokes exactly one application
service, and returns the standardized envelope (401 §9, INV-02/03). FastAPI is an
*optional* dependency, imported lazily so the core stays framework-free
(400 §9, INV-08). The endpoints use the seeded demo configuration so the full
student journey works out of the box.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...application.container import Backend
from ...application.dto import ErrorCode, ServiceResult
from ...application import seed
from ...domain.common.identifiers import RecommendationId, StudentId
from ...engines.agent.types import AgentInput
from ...engines.assessment.definitions import AssessmentDefinition
from ...engines.assessment.engine import AssessmentInput
from ...engines.assessment.responses import AssessmentSubmission, ItemResponse
from ...engines.retrieval.engine import RetrievalInput
from .envelope import http_status, to_envelope

_STATIC_DIR = Path(__file__).parent / "static"


def _serialize_assessment(defn: AssessmentDefinition) -> dict:
    return {
        "id": defn.id,
        "version": defn.version.number,
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "questions": [
                    {
                        "id": q.id,
                        "prompt": q.prompt,
                        "construct": q.construct,
                        "scale_min": q.scale_min,
                        "scale_max": q.scale_max,
                    }
                    for q in s.questions
                ],
            }
            for s in defn.sections
        ],
    }


def create_app(backend: Backend | None = None) -> Any:
    """Build the FastAPI app. Defaults to the fully-seeded demo backend."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "FastAPI is not installed. Install with: pip install 'detective-monkey[api]'"
        ) from exc

    backend = backend or seed.build_demo_backend()
    definition = seed.default_assessment_definition()
    feature_defs = seed.default_feature_definitions()
    reasoning = seed.default_reasoning_config()
    weights = seed.default_weights()
    knowledge_nodes = seed.demo_knowledge_nodes()

    app = FastAPI(title="Detective Monkey", version="2.0.0")

    def _respond(result: ServiceResult) -> "JSONResponse":
        return JSONResponse(content=to_envelope(result), status_code=http_status(result))

    # -- health (60 §16) ---------------------------------------------------

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"success": True, "data": {"status": "healthy"}, "errors": [],
                "warnings": [], "metadata": {}}

    @app.get("/api/v1/readyz")
    def ready() -> dict:
        return {"success": True, "data": {"status": "ready"}, "errors": [],
                "warnings": [], "metadata": {}}

    # -- assessment flow ---------------------------------------------------

    @app.get("/api/v1/assessments/default")
    def get_assessment() -> dict:
        return {"success": True, "data": _serialize_assessment(definition),
                "errors": [], "warnings": [], "metadata": {}}

    @app.post("/api/v1/students/{student_id}/assessment")
    def submit_assessment(student_id: str, body: dict):
        answers = (body or {}).get("answers", [])
        try:
            responses = tuple(
                ItemResponse(
                    question_id=str(a["question_id"]),
                    value=float(a["value"]) if a.get("value") is not None else None,
                    duration_ms=int(a["duration_ms"]) if a.get("duration_ms") else None,
                )
                for a in answers
            )
        except (KeyError, TypeError, ValueError):
            return _respond(ServiceResult.fail(
                ErrorCode.VALIDATION_ERROR, "Malformed answers payload."))

        sid = StudentId(student_id)
        submission = AssessmentSubmission(sid, definition.id, definition.version, responses)
        submit_result = backend.submit_assessment.execute(
            AssessmentInput(definition, submission))
        if not submit_result.success:
            return _respond(submit_result)
        # Analysis step: build the profile immediately (Assessment Flow §7).
        return _respond(backend.generate_profile.execute(sid, feature_defs, reasoning))

    # -- profile / recommendations / explanation ---------------------------

    @app.get("/api/v1/students/{student_id}/profile")
    def get_profile(student_id: str):
        profile = backend.profiles.get_active(StudentId(student_id))
        if profile is None:
            return _respond(ServiceResult.fail(ErrorCode.NOT_FOUND, "No active profile."))
        from ...application.services import _profile_dto
        return _respond(ServiceResult.ok(_profile_dto(profile)))

    @app.post("/api/v1/students/{student_id}/recommendations")
    def generate_recommendations(student_id: str):
        return _respond(backend.generate_recommendations.execute(
            StudentId(student_id), weights))

    @app.get("/api/v1/students/{student_id}/recommendations")
    def list_recommendations(student_id: str):
        from ...application.dto import RecommendationDTO, RecommendationListDTO
        recs = backend.recommendations.list_for_student(StudentId(student_id))
        dto = RecommendationListDTO(
            student_id=student_id,
            recommendations=tuple(
                RecommendationDTO(r.id.value, r.career_id.value, r.overall_score.value,
                                  r.confidence.value.value, len(r.skill_gaps))
                for r in recs
            ),
        )
        return _respond(ServiceResult.ok(dto))

    @app.get("/api/v1/recommendations/{recommendation_id}/explanation")
    def explain(recommendation_id: str):
        return _respond(backend.explain_recommendation.execute(
            RecommendationId(recommendation_id)))

    # -- AI coach ----------------------------------------------------------

    @app.post("/api/v1/conversations")
    def converse(body: dict):
        message = (body or {}).get("message", "")
        retrieval = RetrievalInput(
            query=message,
            knowledge_nodes=knowledge_nodes,
            vector_index=backend.vector_index,
        )
        return _respond(backend.ask_agent.execute(
            AgentInput(message=message, retrieval_input=retrieval)))

    # -- static SPA (mounted last so /api routes win) ----------------------

    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")

    app.state.backend = backend
    return app
