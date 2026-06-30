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
from ...domain.common.identifiers import StudentId
from ...engines.agent.types import AgentInput
from ...engines.assessment.definitions import AssessmentDefinition
from ...engines.assessment.engine import AssessmentInput
from ...engines.assessment.responses import AssessmentSubmission, ItemResponse
from ...engines.intelligence import ConversationContext, StudentPreferences
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

        # Optional conversation + preferences enrich the Intelligence Engine.
        conv_text = (body or {}).get("conversation")
        conversation = ConversationContext((conv_text,)) if conv_text else None
        prefs_in = (body or {}).get("preferences") or {}
        preferences = StudentPreferences(
            dream_careers=tuple(prefs_in.get("dream_careers", [])),
            preferred_countries=tuple(prefs_in.get("preferred_countries", [])),
            work_preferences=tuple(prefs_in.get("work_preferences", [])),
            max_study_years=prefs_in.get("max_study_years"),
            remote_only=bool(prefs_in.get("remote_only", False)),
        ) if prefs_in else None

        # The Intelligence Engine is the single reasoning component (Analysis step).
        return _respond(backend.intelligence.build_from_assessment(
            AssessmentInput(definition, submission), conversation, preferences))

    # -- intelligence: dashboard / summary ---------------------------------

    @app.get("/api/v1/students/{student_id}/dashboard")
    def get_dashboard(student_id: str):
        return _respond(backend.intelligence.dashboard(StudentId(student_id)))

    @app.get("/api/v1/students/{student_id}/intelligence")
    def get_intelligence(student_id: str):
        return _respond(backend.intelligence.get_summary(StudentId(student_id)))

    @app.get("/api/v1/students/{student_id}/profile")
    def get_profile(student_id: str):
        return _respond(backend.intelligence.get_summary(StudentId(student_id)))

    # -- recommendations (premium cards) -----------------------------------

    @app.post("/api/v1/students/{student_id}/recommendations")
    def generate_recommendations(student_id: str):
        return _respond(backend.intelligence.recommend(StudentId(student_id)))

    @app.get("/api/v1/students/{student_id}/recommendations")
    def list_recommendations(student_id: str):
        return _respond(backend.intelligence.recommend(StudentId(student_id)))

    # -- career detail / roadmap / skill gap / comparison ------------------

    @app.get("/api/v1/students/{student_id}/careers/{career_id}")
    def career_detail(student_id: str, career_id: str):
        return _respond(backend.intelligence.career_detail(StudentId(student_id), career_id))

    @app.get("/api/v1/students/{student_id}/careers/{career_id}/roadmap")
    def career_roadmap(student_id: str, career_id: str):
        return _respond(backend.intelligence.roadmap(StudentId(student_id), career_id))

    @app.get("/api/v1/students/{student_id}/careers/{career_id}/skill-gap")
    def career_skill_gap(student_id: str, career_id: str):
        return _respond(backend.intelligence.skill_gap(StudentId(student_id), career_id))

    @app.get("/api/v1/students/{student_id}/compare")
    def compare_careers(student_id: str, a: str, b: str):
        return _respond(backend.intelligence.compare(StudentId(student_id), a, b))

    # -- downloadable AI report --------------------------------------------

    @app.get("/api/v1/students/{student_id}/report")
    def report(student_id: str):
        from fastapi.responses import HTMLResponse, JSONResponse as _JSON
        result = backend.intelligence.report_html(StudentId(student_id))
        if not result.success:
            return _JSON(content=to_envelope(result), status_code=http_status(result))
        return HTMLResponse(content=result.data)

    # -- AI coach (context-aware, Epic 4) ----------------------------------

    @app.post("/api/v1/conversations")
    def converse(body: dict):
        message = (body or {}).get("message", "")
        student_id = (body or {}).get("student_id")
        retrieval = RetrievalInput(
            query=message, knowledge_nodes=knowledge_nodes, vector_index=backend.vector_index)
        agent = backend.ask_agent.execute(AgentInput(message=message, retrieval_input=retrieval))
        grounded = agent.data.response if agent.success and agent.data else ""
        if student_id:
            return _respond(backend.intelligence.coach(StudentId(student_id), message, grounded))
        return _respond(agent)

    # -- static SPA (mounted last so /api routes win) ----------------------

    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")

    app.state.backend = backend
    return app
