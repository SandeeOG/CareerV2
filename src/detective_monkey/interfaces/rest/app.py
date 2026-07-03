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

    # -- Student Evidence Engine (STUDENT_EVIDENCE_ENGINE_V1) ----------------
    # The primary source of student information: expanded assessment, evidence
    # profile, human validation and the six-monthly Career Pulse.

    @app.get("/api/v1/evidence/assessment")
    def evidence_assessment():
        return _respond(backend.evidence.definition())

    @app.post("/api/v1/students/{student_id}/evidence")
    def submit_evidence(student_id: str, body: dict):
        return _respond(backend.evidence.submit(StudentId(student_id), body or {}))

    @app.get("/api/v1/students/{student_id}/evidence")
    def get_evidence(student_id: str):
        return _respond(backend.evidence.evidence(StudentId(student_id)))

    @app.post("/api/v1/students/{student_id}/evidence/validation")
    def validate_evidence(student_id: str, body: dict):
        verdict = str((body or {}).get("verdict", "partially"))
        inaccurate = tuple(str(f) for f in (body or {}).get("inaccurate", []))
        return _respond(backend.evidence.validate(StudentId(student_id), verdict, inaccurate))

    @app.get("/api/v1/students/{student_id}/pulse")
    def pulse_status(student_id: str):
        return _respond(backend.evidence.pulse_status(StudentId(student_id)))

    @app.post("/api/v1/students/{student_id}/pulse")
    def submit_pulse(student_id: str, body: dict):
        return _respond(backend.evidence.submit_pulse(StudentId(student_id), body or {}))

    @app.get("/api/v1/students/{student_id}/home")
    def student_home(student_id: str):
        return _respond(backend.evidence.home(StudentId(student_id)))

    # -- Discovery loop: hypotheses → experiments → reflection → recalibration

    @app.get("/api/v1/students/{student_id}/experiments")
    def list_experiments(student_id: str):
        return _respond(backend.discovery.overview(StudentId(student_id)))

    @app.get("/api/v1/students/{student_id}/hypotheses")
    def list_hypotheses(student_id: str):
        return _respond(backend.discovery.hypotheses(StudentId(student_id)))

    @app.post("/api/v1/students/{student_id}/experiments/{experiment_id}/accept")
    def accept_experiment(student_id: str, experiment_id: str):
        return _respond(backend.discovery.accept(StudentId(student_id), experiment_id))

    @app.post("/api/v1/students/{student_id}/experiments/{experiment_id}/skip")
    def skip_experiment(student_id: str, experiment_id: str):
        return _respond(backend.discovery.skip(StudentId(student_id), experiment_id))

    @app.post("/api/v1/students/{student_id}/experiments/{experiment_id}/complete")
    def complete_experiment(student_id: str, experiment_id: str, body: dict):
        return _respond(backend.discovery.complete(
            StudentId(student_id), experiment_id, body or {}))

    # -- intelligence: dashboard / summary ---------------------------------
    # Derived state (intelligence profile, affinities) lives in memory and is
    # rebuilt deterministically from the persisted evidence profile on first
    # touch after a restart.

    def _ready(student_id: str) -> StudentId:
        sid = StudentId(student_id)
        backend.evidence.ensure_ready(sid)
        return sid

    @app.get("/api/v1/students/{student_id}/dashboard")
    def get_dashboard(student_id: str):
        return _respond(backend.intelligence.dashboard(_ready(student_id)))

    @app.get("/api/v1/students/{student_id}/intelligence")
    def get_intelligence(student_id: str):
        return _respond(backend.intelligence.get_summary(_ready(student_id)))

    @app.get("/api/v1/students/{student_id}/profile")
    def get_profile(student_id: str):
        return _respond(backend.intelligence.get_summary(_ready(student_id)))

    # -- recommendations (premium cards) -----------------------------------

    @app.post("/api/v1/students/{student_id}/recommendations")
    def generate_recommendations(student_id: str):
        return _respond(backend.intelligence.recommend(_ready(student_id)))

    @app.get("/api/v1/students/{student_id}/recommendations")
    def list_recommendations(student_id: str):
        return _respond(backend.intelligence.recommend(_ready(student_id)))

    # -- career detail / roadmap / skill gap / comparison ------------------

    @app.get("/api/v1/students/{student_id}/careers/{career_id}")
    def career_detail(student_id: str, career_id: str):
        return _respond(backend.intelligence.career_detail(_ready(student_id), career_id))

    @app.get("/api/v1/students/{student_id}/careers/{career_id}/roadmap")
    def career_roadmap(student_id: str, career_id: str):
        return _respond(backend.intelligence.roadmap(_ready(student_id), career_id))

    @app.get("/api/v1/students/{student_id}/careers/{career_id}/skill-gap")
    def career_skill_gap(student_id: str, career_id: str):
        return _respond(backend.intelligence.skill_gap(_ready(student_id), career_id))

    @app.get("/api/v1/students/{student_id}/compare")
    def compare_careers(student_id: str, a: str, b: str):
        return _respond(backend.intelligence.compare(_ready(student_id), a, b))

    # -- downloadable AI report --------------------------------------------

    @app.get("/api/v1/students/{student_id}/report")
    def report(student_id: str):
        from fastapi.responses import HTMLResponse, JSONResponse as _JSON
        result = backend.intelligence.report_html(_ready(student_id))
        if not result.success:
            return _JSON(content=to_envelope(result), status_code=http_status(result))
        return HTMLResponse(content=result.data)

    # -- AI coach (context-aware, Epic 4) ----------------------------------

    @app.post("/api/v1/conversations")
    def converse(body: dict):
        message = (body or {}).get("message", "")
        student_id = (body or {}).get("student_id")
        # The coach retrieves from the Knowledge Platform graph — career
        # profiles are first-class knowledge entities there (38/39); no
        # hardcoded career descriptions exist anywhere in this path.
        retrieval = RetrievalInput(
            query=message,
            knowledge_nodes=backend.knowledge_graph.list_nodes(),
            vector_index=backend.vector_index)
        agent = backend.ask_agent.execute(AgentInput(message=message, retrieval_input=retrieval))
        grounded = agent.data.response if agent.success and agent.data else ""
        if student_id:
            return _respond(backend.intelligence.coach(StudentId(student_id), message, grounded))
        return _respond(agent)

    # -- Explore Careers: the Career Knowledge Base (38/39) ------------------
    # Independent from recommendations: students freely browse 16 industries
    # and ~300 broad career paths, all served from the single knowledge layer.

    def _ok(data) -> dict:
        return {"success": True, "data": data, "errors": [], "warnings": [],
                "metadata": {}}

    def _err(message: str, status: int = 404) -> "JSONResponse":
        return JSONResponse(status_code=status, content={
            "success": False, "data": None, "warnings": [], "metadata": {},
            "errors": [{"code": "NOT_FOUND", "message": message}]})

    def _career_card(p) -> dict:
        return {
            "id": p.id, "name": p.name, "industry": p.industry,
            "career_family": p.career_family, "student_summary": p.student_summary,
            "tags": list(p.tags[:4]), "difficulty": p.difficulty,
            "salary_entry_lpa": p.salary_entry_lpa,
            "salary_senior_lpa": p.salary_senior_lpa,
            "future_demand": p.future_demand, "remote_work": p.remote_work,
            "automation_risk": p.automation_risk,
        }

    @app.get("/api/v1/careers/industries")
    def list_industries():
        repo = backend.career_knowledge
        if repo is None:
            return _err("Career knowledge base not loaded.", 503)
        return _ok([{
            "id": i.id, "name": i.name, "icon": i.icon,
            "description": i.description,
            "career_count": len(repo.careers_in(i.id)),
            "featured_careers": list(i.featured_careers),
            "trending_careers": list(i.trending_careers),
            "future_note": i.future_note,
        } for i in repo.industries()])

    @app.get("/api/v1/careers/industries/{industry_id}")
    def industry_careers(industry_id: str):
        repo = backend.career_knowledge
        if repo is None:
            return _err("Career knowledge base not loaded.", 503)
        industry = repo.industry(industry_id)
        if industry is None:
            return _err("Industry not found.")
        return _ok({
            "id": industry.id, "name": industry.name, "icon": industry.icon,
            "description": industry.description, "future_note": industry.future_note,
            "careers": [_career_card(p) for p in repo.careers_in(industry_id)],
        })

    @app.get("/api/v1/careers/search")
    def search_careers(q: str = "", industry: str = "", remote: bool = False,
                       ai_safe: bool = False, government: bool = False,
                       freelancing: bool = False, entrepreneurship: bool = False,
                       creativity: bool = False, leadership: bool = False,
                       outdoor: bool = False, people: bool = False,
                       no_programming: bool = False, mathematics: bool = False,
                       max_difficulty: int = 0, min_salary: int = 0,
                       education: str = "", country: str = ""):
        repo = backend.career_knowledge
        if repo is None:
            return _err("Career knowledge base not loaded.", 503)
        from ...knowledge.careers import CareerSearchFilters
        filters = CareerSearchFilters(
            industry=industry, max_difficulty=max_difficulty,
            min_salary_lpa=min_salary, remote=remote, ai_safe=ai_safe,
            government=government, freelancing=freelancing,
            entrepreneurship=entrepreneurship, creativity=creativity,
            leadership=leadership, travel_or_outdoor=outdoor,
            people_facing=people, education_keyword=education, country=country,
            requires_programming=False if no_programming else None,
            requires_mathematics=True if mathematics else None,
        )
        return _ok([_career_card(p) for p in repo.search(q, filters)])

    @app.get("/api/v1/careers/{career_id}")
    def career_profile(career_id: str):
        repo = backend.career_knowledge
        if repo is None:
            return _err("Career knowledge base not loaded.", 503)
        profile = repo.get(career_id)
        if profile is None:
            return _err("Career not found.")
        from ...knowledge.careers.schema import profile_to_json
        data = profile_to_json(profile)
        data["related_profiles"] = [_career_card(p) for p in repo.related(career_id)]
        industry = repo.industry(profile.industry)
        data["industry_name"] = industry.name if industry else profile.industry
        return _ok(data)

    # -- static SPA (mounted last so /api routes win) ----------------------

    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="spa")

    app.state.backend = backend
    return app
