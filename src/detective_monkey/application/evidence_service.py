"""Application service for the Student Evidence Engine.

Orchestrates the evidence lifecycle: expanded assessment → Student Evidence
Profile → intelligence profile → dashboard/home aggregates, human validation
and the six-monthly Career Pulse. Owns no reasoning: the Evidence Engine builds
the profile, the Intelligence Engine interprets it, ranking recommends from it.

Returns plain-dict payloads inside the standard ServiceResult envelope (the
Explore Careers endpoints already follow this style).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..domain.common.identifiers import StudentId
from ..engines.intelligence import ConversationContext, StudentPreferences
from ..engines.student_evidence import (
    CAREER_PULSE,
    EVIDENCE_ASSESSMENT,
    EvidenceSubmission,
    OpenResponse,
    StructuredAnswer,
    StudentEvidenceEngine,
    StudentEvidenceProfile,
    StudentGoalsInfo,
    StudentProfileInfo,
    assessment_to_json,
    profile_to_json,
    to_assessment_result,
)
from ..engines.student_evidence.affinity import affinity_map
from ..engines.student_evidence.schema import AcademicRecord
from .dto import ErrorCode, ServiceResult

# Which canonical features read as "interests" vs "strengths" in the UI.
_INTEREST_FEATURES = (
    "technical_interest", "business_interest", "artistic_interest",
    "research_interest", "helping_others", "hands_on_work",
    "people_interaction", "curiosity", "entrepreneurship",
)
_STRENGTH_FEATURES = (
    "analytical_thinking", "creativity", "leadership", "communication",
    "problem_solving", "attention_to_detail", "teamwork", "independence",
)

_FEATURE_LABELS = {
    "technical_interest": "Technology", "business_interest": "Business",
    "artistic_interest": "Creative Arts", "research_interest": "Research & Science",
    "helping_others": "Helping Others", "hands_on_work": "Hands-on Work",
    "people_interaction": "Working with People", "curiosity": "Curiosity",
    "entrepreneurship": "Entrepreneurship", "analytical_thinking": "Analytical Thinking",
    "creativity": "Creativity", "leadership": "Leadership",
    "communication": "Communication", "problem_solving": "Problem Solving",
    "attention_to_detail": "Attention to Detail", "teamwork": "Teamwork",
    "independence": "Independence", "risk_tolerance": "Risk Tolerance",
    "learning_style": "Learning by Doing", "relocation_preference": "Open to Relocating",
    "international_interest": "Global Outlook", "career_confidence": "Career Clarity",
}


def _label(feature: str) -> str:
    return _FEATURE_LABELS.get(feature, feature.replace("_", " ").title())


class EvidenceApplicationService:
    def __init__(
        self,
        engine: StudentEvidenceEngine,
        evidence_profiles,          # EvidenceProfileRepository
        intelligence,               # IntelligenceApplicationService
        career_knowledge=None,      # CareerKnowledgeRepository | None
        llm: object | None = None,
        affinities: dict | None = None,
    ) -> None:
        self._engine = engine
        self._repo = evidence_profiles
        self._intelligence = intelligence
        self._knowledge = career_knowledge
        self._llm = llm
        self._affinities = affinities if affinities is not None else {}
        self._discovery = None  # attached by the composition root

    def attach_discovery(self, discovery) -> None:
        """Late-bound link to the discovery service (composition root only)."""
        self._discovery = discovery

    def ensure_ready(self, student_id: StudentId) -> bool:
        """Lazy rebuild after a restart: derived state (intelligence profile,
        affinities) is deterministic, so it is recomputed from the persisted
        Student Evidence Profile on first touch rather than stored."""
        summary = self._intelligence.get_summary(student_id)
        if summary.success:
            return True
        profile = self._repo.get(student_id)
        if profile is None:
            return False
        self._rebuild_intelligence(student_id, profile)
        return True

    def rebuild(self, student_id: StudentId, profile: StudentEvidenceProfile) -> None:
        """Public recalibration entry point for the discovery loop."""
        self._rebuild_intelligence(student_id, profile)

    # -- definitions ---------------------------------------------------------

    def definition(self) -> ServiceResult[dict]:
        return ServiceResult.ok(assessment_to_json(EVIDENCE_ASSESSMENT))

    # -- submit --------------------------------------------------------------

    def submit(self, student_id: StudentId, payload: dict) -> ServiceResult[dict]:
        try:
            submission = _parse_submission(student_id, payload or {})
        except (KeyError, TypeError, ValueError) as exc:
            return ServiceResult.fail(ErrorCode.VALIDATION_ERROR,
                                      f"Malformed evidence payload: {exc}")
        if not submission.structured_answers and not submission.open_responses:
            return ServiceResult.fail(ErrorCode.VALIDATION_ERROR,
                                      "At least one answer is required.")

        profile = self._engine.build(submission, llm=self._llm)
        self._repo.save(student_id, profile)
        self._rebuild_intelligence(student_id, profile)

        return ServiceResult.ok({
            "student_id": student_id.value,
            "snapshot": self._snapshot(profile),
            "validation": _validation_view(profile),
        })

    # -- read ----------------------------------------------------------------

    def evidence(self, student_id: StudentId) -> ServiceResult[dict]:
        profile = self._repo.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        self.ensure_ready(student_id)
        data = profile_to_json(profile)
        data["snapshot"] = self._snapshot(profile)
        data["validation"] = _validation_view(profile)
        return ServiceResult.ok(data)

    # -- human validation ------------------------------------------------------

    def validate(self, student_id: StudentId, verdict: str,
                 inaccurate: tuple[str, ...]) -> ServiceResult[dict]:
        profile = self._repo.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        updated = self._engine.apply_validation(profile, verdict, inaccurate)
        self._repo.save(student_id, updated)
        # Corrections flow straight through to recommendations.
        self._rebuild_intelligence(student_id, updated)
        return ServiceResult.ok({
            "student_id": student_id.value,
            "validation_status": updated.metadata.validation_status,
            "snapshot": self._snapshot(updated),
        })

    # -- Career Pulse -----------------------------------------------------------

    def pulse_status(self, student_id: StudentId) -> ServiceResult[dict]:
        profile = self._repo.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        available = self._engine.pulse_due(profile)
        data = {
            "available": available,
            "estimated_minutes": 5,
            "last_pulse_at": profile.metadata.last_pulse_at,
            "last_assessment_at": profile.metadata.created_at,
        }
        if available:
            data["definition"] = assessment_to_json(CAREER_PULSE)
        return ServiceResult.ok(data)

    def submit_pulse(self, student_id: StudentId, payload: dict) -> ServiceResult[dict]:
        profile = self._repo.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        structured, open_responses = _parse_answers(payload or {}, CAREER_PULSE)
        if not structured and not open_responses:
            return ServiceResult.fail(ErrorCode.VALIDATION_ERROR,
                                      "At least one answer is required.")
        updated = self._engine.apply_pulse(profile, structured, open_responses,
                                           llm=self._llm)
        self._repo.save(student_id, updated)
        self._rebuild_intelligence(student_id, updated)
        return ServiceResult.ok({
            "student_id": student_id.value,
            "snapshot": self._snapshot(updated),
        })

    # -- personalized dashboard aggregate ----------------------------------------

    def home(self, student_id: StudentId) -> ServiceResult[dict]:
        profile = self._repo.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        self.ensure_ready(student_id)

        matches = self._top_matches(student_id, 5)
        confidence_feature = profile.feature("career_confidence")
        data = {
            "student_id": student_id.value,
            "welcome": {
                "name": profile.profile.name,
                "grade": profile.profile.grade,
                "school": profile.profile.school,
                "career_confidence": round((confidence_feature.score if confidence_feature else 0.5) * 100),
                "last_assessment_at": profile.metadata.created_at,
                "validation_status": profile.metadata.validation_status,
            },
            "snapshot": self._snapshot(profile, matches),
            "matches": matches,
            "growth": _growth(profile),
            "pulse": {"available": self._engine.pulse_due(profile), "estimated_minutes": 5},
            "insight": self._daily_insight(),
            "learning": self._recommended_learning(matches),
        }
        # The discovery loop leads the dashboard: the next experiment and the
        # momentum of tested beliefs (not a "% complete" checklist).
        if self._discovery is not None:
            data["next_experiment"] = self._discovery.next_experiment(student_id)
            data["momentum"] = self._discovery.momentum(student_id)
            for m in matches:
                known = self._knowledge.get(m["career_id"]) if self._knowledge else None
                m["evidence_strength"] = (
                    self._discovery.strength_for(student_id, profile, known)
                    if known is not None else 0)
        return ServiceResult.ok(data)

    # -- assembly helpers ----------------------------------------------------

    def _rebuild_intelligence(self, student_id: StudentId,
                              profile: StudentEvidenceProfile) -> None:
        """Recommendations consume only the Student Evidence Profile — this
        renders it as structured construct evidence for the deterministic
        Intelligence Engine (never raw responses), and refreshes the
        evidence→career affinity bonuses used by ranking."""
        if self._knowledge is not None and self._knowledge.count() > 0:
            self._affinities[student_id.value] = affinity_map(
                profile, self._knowledge.all_profiles())
        result = to_assessment_result(profile)
        conversation = None
        texts = tuple(r.text for r in profile.assessment.open_responses)
        if texts:
            conversation = ConversationContext(texts)
        preferences = _preferences(profile.goals)
        self._intelligence.build_from_evidence(student_id, result, conversation, preferences)

    def _snapshot(self, profile: StudentEvidenceProfile,
                  matches: list[dict] | None = None) -> dict:
        features = dict(profile.extracted_features)

        def top(names: tuple[str, ...], n: int) -> list[dict]:
            pairs = [(k, features[k]) for k in names if k in features]
            pairs.sort(key=lambda p: -p[1].score)
            return [{"feature": k, "label": _label(k),
                     "score": round(v.score * 100),
                     "confidence": round(v.confidence * 100),
                     "evidence": list(v.evidence[:2])} for k, v in pairs[:n]]

        work_style = profile.goals.preferred_work_style
        if not work_style:
            team = features.get("teamwork")
            solo = features.get("independence")
            if team and solo:
                work_style = "collaborative" if team.score >= solo.score else "independent"

        industries: list[str] = []
        if matches:
            industries = list(dict.fromkeys(
                m["industry_name"] for m in matches if m.get("industry_name")))[:3]

        confidence_feature = features.get("career_confidence")
        return {
            "top_interests": top(_INTEREST_FEATURES, 3),
            "top_strengths": top(_STRENGTH_FEATURES, 3),
            "work_style": work_style,
            "preferred_industries": industries,
            "career_confidence": round((confidence_feature.score if confidence_feature else 0.5) * 100),
            "recommendation_confidence": self._recommendation_confidence(profile),
            "sources_used": list(profile.metadata.sources_used),
            "extraction_provider": profile.metadata.extraction_provider,
        }

    def _recommendation_confidence(self, profile: StudentEvidenceProfile) -> int:
        summary = self._intelligence.get_summary(StudentId(profile.student_id))
        if summary.success and summary.data is not None:
            return round(summary.data.confidence * 100)
        return 0

    def _top_matches(self, student_id: StudentId, n: int) -> list[dict]:
        recs = self._intelligence.recommend(student_id)
        if not recs.success or recs.data is None:
            return []
        cards = []
        for card in recs.data.cards[:n]:
            industry_name = ""
            if self._knowledge is not None:
                known = self._knowledge.get(card.career_id)
                if known is not None:
                    industry = self._knowledge.industry(known.industry)
                    industry_name = industry.name if industry else known.industry
            cards.append({
                "career_id": card.career_id,
                "name": card.name,
                "score": round(card.score),
                "confidence": round(card.confidence * 100),
                "industry_name": industry_name,
                "why": card.match_explanation[0] if card.match_explanation else "",
                "salary_range": card.salary_range,
                "future_demand": card.future_demand,
            })
        return cards

    def _daily_insight(self) -> dict:
        """One rotating insight per day, computed from the knowledge base."""
        if self._knowledge is None or self._knowledge.count() == 0:
            return {"title": "Did you know?",
                    "detail": "There are hundreds of career paths beyond the famous ten — explore an industry today."}
        profiles = self._knowledge.all_profiles()
        insights = []
        fastest = max(profiles, key=lambda p: p.future_demand)
        insights.append(("Fastest growing career",
                         f"{fastest.name} shows the strongest future demand in our knowledge base "
                         f"({round(fastest.future_demand * 100)}%). {fastest.student_summary}",
                         fastest.id))
        paying = max(profiles, key=lambda p: p.salary_senior_lpa)
        insights.append(("Highest paying path",
                         f"Senior professionals in {paying.name} can earn up to "
                         f"₹{paying.salary_senior_lpa} LPA in India.", paying.id))
        remote = max(profiles, key=lambda p: p.remote_work)
        insights.append(("Most remote-friendly",
                         f"{remote.name} is one of the most remote-compatible careers "
                         f"({round(remote.remote_work * 100)}%). Work from anywhere.", remote.id))
        safe = min(profiles, key=lambda p: p.automation_risk)
        insights.append(("AI-resilient career",
                         f"{safe.name} has one of the lowest automation risks "
                         f"({round(safe.automation_risk * 100)}%). {safe.ai_impact[:140]}", safe.id))
        entrepreneurial = max(profiles, key=lambda p: p.entrepreneurship)
        insights.append(("Best for founders",
                         f"{entrepreneurial.name} offers outstanding entrepreneurship scope — "
                         f"many professionals build their own ventures.", entrepreneurial.id))
        title, detail, career_id = insights[
            datetime.now(timezone.utc).timetuple().tm_yday % len(insights)]
        return {"title": title, "detail": detail, "career_id": career_id}

    def _recommended_learning(self, matches: list[dict]) -> dict:
        """Books / courses / projects drawn from the student's top match."""
        if not matches or self._knowledge is None:
            return {}
        top = self._knowledge.get(matches[0]["career_id"])
        if top is None:
            return {}
        return {
            "for_career": top.name,
            "career_id": top.id,
            "books": list(top.books[:2]),
            "courses": list(top.courses[:2]),
            "projects": list((top.portfolio_ideas + top.projects)[:2]),
            "communities": list(top.communities[:2]),
        }


# -- parsing / views ----------------------------------------------------------


def _parse_submission(student_id: StudentId, payload: dict) -> EvidenceSubmission:
    profile_in = payload.get("profile") or {}
    goals_in = payload.get("goals") or {}
    academic_in = payload.get("academic") or []

    age = profile_in.get("age")
    profile = StudentProfileInfo(
        name=str(profile_in.get("name", "")).strip(),
        age=int(age) if age not in (None, "") else None,
        grade=str(profile_in.get("grade", "")).strip(),
        school=str(profile_in.get("school", "")).strip(),
        city=str(profile_in.get("city", "")).strip(),
        state=str(profile_in.get("state", "")).strip(),
        country=str(profile_in.get("country", "")).strip(),
        board=str(profile_in.get("board", "")).strip(),
    )
    goals = StudentGoalsInfo(
        dream_career=str(goals_in.get("dream_career", "")).strip(),
        preferred_country=str(goals_in.get("preferred_country", "")).strip(),
        preferred_subjects=tuple(str(s) for s in goals_in.get("preferred_subjects", [])),
        preferred_work_style=str(goals_in.get("preferred_work_style", "")).strip(),
        sector_preference=str(goals_in.get("sector_preference", "")).strip(),
        entrepreneurship_interest=str(goals_in.get("entrepreneurship_interest", "")).strip(),
        willing_to_relocate=str(goals_in.get("willing_to_relocate", "")).strip(),
    )
    academic = tuple(
        AcademicRecord(
            subject=str(a["subject"]).strip(),
            average_score=float(a["average_score"]),
            trend=str(a.get("trend", "stable")),
            grade=str(a.get("grade", "")),
            academic_year=str(a.get("academic_year", "")),
        )
        for a in academic_in if str(a.get("subject", "")).strip()
    )
    structured, open_responses = _parse_answers(payload, EVIDENCE_ASSESSMENT)
    return EvidenceSubmission(
        student_id=student_id, profile=profile, academic=academic, goals=goals,
        structured_answers=structured, open_responses=open_responses,
    )


def _parse_answers(payload: dict, assessment) -> tuple[tuple[StructuredAnswer, ...],
                                                       tuple[OpenResponse, ...]]:
    structured: list[StructuredAnswer] = []
    for a in payload.get("answers", []):
        qid = str(a.get("question_id", ""))
        if not qid:
            continue
        value = a.get("value")
        selected = a.get("selected") or []
        structured.append(StructuredAnswer(
            question_id=qid,
            value=float(value) if value is not None else None,
            selected=tuple(str(s) for s in selected),
        ))
    open_responses: list[OpenResponse] = []
    for a in payload.get("open_answers", []):
        qid = str(a.get("question_id", ""))
        text = str(a.get("text", "")).strip()
        if not qid or not text:
            continue
        question = assessment.question(qid)
        open_responses.append(OpenResponse(
            question_id=qid,
            prompt=question.prompt if question else "",
            text=text[:2000],
        ))
    return tuple(structured), tuple(open_responses)


def _validation_view(profile: StudentEvidenceProfile) -> dict:
    """The human-in-the-loop view: 'Your strongest qualities — does this
    accurately describe you?'"""
    return {
        "status": profile.metadata.validation_status,
        "question": "Does this accurately describe you?",
        "qualities": [
            {"feature": k, "label": _label(k), "score": round(v.score * 100),
             "evidence": list(v.evidence[:2])}
            for k, v in profile.top_features(4, exclude=("learning_style",))
        ],
    }


def _growth(profile: StudentEvidenceProfile) -> dict:
    total_q = profile.assessment.structured_total + profile.assessment.open_total
    answered = profile.assessment.structured_answered + profile.assessment.open_answered
    items = [
        ("Assessment completed", profile.assessment.completion >= 0.8,
         f"{answered}/{total_q} questions answered"),
        ("Evidence collected", len(profile.extracted_features) >= 8,
         f"{len(profile.extracted_features)} features extracted"),
        ("Academic data", len(profile.academic) > 0,
         f"{len(profile.academic)} subjects imported" if profile.academic
         else "Import marks to sharpen matches"),
        ("Career goals set", not profile.goals.is_empty,
         profile.goals.dream_career or "Tell us your dream career"),
        ("Profile verified", profile.metadata.validation_status in ("yes", "partially"),
         "You confirmed your profile" if profile.metadata.validation_status in ("yes", "partially")
         else "Review your strengths"),
    ]
    done = sum(1 for _, ok, _ in items if ok)
    return {
        "percent": round(done / len(items) * 100),
        "items": [{"label": label, "done": ok, "detail": detail}
                  for label, ok, detail in items],
    }


def _preferences(goals: StudentGoalsInfo) -> StudentPreferences | None:
    if goals.is_empty:
        return None
    return StudentPreferences(
        dream_careers=(goals.dream_career,) if goals.dream_career else (),
        preferred_countries=(goals.preferred_country,) if goals.preferred_country else (),
        work_preferences=(goals.preferred_work_style,) if goals.preferred_work_style else (),
        remote_only=goals.preferred_work_style == "remote",
    )
