"""Application service for the Intelligence Layer (403_SERVICE_ARCHITECTURE.md).

Orchestrates the single reasoning component (Intelligence Engine + ranker +
mentor derivations) into premium, personalized use-cases: assessment → profile,
dashboard, recommendations, career detail, roadmaps, comparison, skill gaps and
a downloadable report. It owns no reasoning and no persistence logic.
"""

from __future__ import annotations

from ..contracts import EngineRequest, IntelligenceContext
from ..domain.common.events import DomainEvent, EventName
from ..domain.common.identifiers import StudentId
from ..domain.student.student import Student
from ..engines.assessment.engine import AssessmentEngine, AssessmentInput
from ..engines.intelligence import (
    CareerRecommendation,
    ConversationContext,
    IntelligenceEngine,
    StudentIntelligenceProfile,
    StudentPreferences,
    mentor,
    rank_careers,
)
from .dto import ErrorCode, EvidenceDTO, IntelligenceSummaryDTO, ServiceResult
from .intelligence_dto import (
    ActionDTO,
    CareerDetailDTO,
    CoachReplyDTO,
    ComparisonDTO,
    ComparisonRowDTO,
    DashboardDTO,
    LearningStyleDTO,
    MissingSkillDTO,
    OpportunityDTO,
    PremiumCardDTO,
    ReadinessDTO,
    RecommendationsDTO,
    RoadmapDTO,
    RoadmapStepDTO,
    SkillGapDTO,
    StrengthDTO,
)

_LEARNING_STYLE_WHY = {
    "analytical": "You learn best by understanding the underlying theory first.",
    "exploratory": "You learn best by exploring and connecting new ideas.",
    "practical": "You learn best by building hands-on projects.",
    "collaborative": "You learn best by working through problems with others.",
    "reflective": "You learn best by reading deeply and reflecting.",
}


def _salary_range(insight) -> str:
    """Human salary band. Knowledge-base insights store LPA (₹ lakhs/year,
    values < 1000); an entry of 0 marks venture paths with variable income."""
    lpa = " LPA" if insight.salary_senior < 1000 else ""
    if insight.salary_entry == 0:
        return f"Variable — up to {insight.currency}{insight.salary_senior:,}{lpa} (own venture)"
    return f"{insight.currency}{insight.salary_entry:,}–{insight.salary_senior:,}{lpa}"


def _band(value: float, labels=("Low", "Moderate", "High", "Very High")) -> str:
    idx = min(len(labels) - 1, int(value * len(labels)))
    return labels[idx]


def _risk_band(value: float) -> str:
    return _band(value, ("Very Low", "Low", "Moderate", "High"))


class IntelligenceApplicationService:
    def __init__(
        self,
        assessment_engine: AssessmentEngine,
        intelligence_engine: IntelligenceEngine,
        careers,
        students,
        profiles,
        publisher,
        insights: dict | None = None,
        memory=None,
    ) -> None:
        self._assessment = assessment_engine
        self._intelligence = intelligence_engine
        self._careers = careers
        self._students = students
        self._profiles = profiles
        self._publisher = publisher
        self._insights = insights or {}
        self._memory = memory

    # -- helpers -----------------------------------------------------------

    def _name(self, career_id: str) -> str:
        from ..domain.common.identifiers import CareerId
        c = self._careers.get(CareerId(career_id))
        return c.identity.canonical_name if c else career_id

    def _matches(self, profile: StudentIntelligenceProfile) -> tuple[CareerRecommendation, ...]:
        return rank_careers(profile, self._careers.list_all())

    def _profile_or_none(self, student_id: StudentId):
        return self._profiles.get(student_id)

    # -- use cases ---------------------------------------------------------

    def build_from_assessment(
        self,
        payload: AssessmentInput,
        conversation: ConversationContext | None = None,
        preferences: StudentPreferences | None = None,
    ) -> ServiceResult[IntelligenceSummaryDTO]:
        student_id = payload.submission.student_id
        ctx = IntelligenceContext(student_id=student_id.value)

        a_resp = self._assessment.execute(EngineRequest(ctx, payload))
        if not a_resp.ok or a_resp.result is None:
            return ServiceResult.fail(
                ErrorCode.VALIDATION_ERROR,
                a_resp.errors[0].message if a_resp.errors else "Assessment failed.")

        if not self._students.exists(student_id):
            self._students.add(Student(id=student_id))
        student = self._students.get(student_id) or Student(id=student_id)
        profile = self._intelligence.build(a_resp.result, student, conversation, preferences)

        self._profiles.save(student_id, profile)
        if self._memory is not None:
            self._memory.record_readiness(student_id, mentor.career_readiness(profile).score)
        self._publisher.publish(DomainEvent(
            EventName.STUDENT_PROFILE_GENERATED, student_id.value,
            aggregate_type="StudentIntelligenceProfile", correlation_id=ctx.correlation_id))
        return ServiceResult.ok(_summary_dto(student_id.value, profile))

    def get_summary(self, student_id: StudentId) -> ServiceResult[IntelligenceSummaryDTO]:
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No intelligence profile yet.")
        return ServiceResult.ok(_summary_dto(student_id.value, profile))

    def dashboard(self, student_id: StudentId) -> ServiceResult[DashboardDTO]:
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No intelligence profile yet.")
        matches = self._matches(profile)
        opportunity = mentor.biggest_opportunity(matches, self._insights)
        action = mentor.todays_recommendation(profile, opportunity)
        readiness = mentor.career_readiness(profile)
        strengths = mentor.strength_views(profile, 5)
        dto = DashboardDTO(
            student_id=student_id.value,
            greeting=self._greeting(student_id),
            ai_summary=mentor.ai_summary(profile, matches, opportunity),
            readiness=ReadinessDTO(readiness.score, readiness.level, readiness.explanation,
                                   readiness.increases, readiness.decreases),
            strengths=tuple(StrengthDTO(s.title, s.confidence, s.explanation) for s in strengths),
            learning_style=LearningStyleDTO(
                profile.learning_style.value,
                _LEARNING_STYLE_WHY.get(profile.learning_style.value, "")),
            opportunity=OpportunityDTO(opportunity.title, opportunity.detail,
                                       opportunity.employability_gain, opportunity.extra_careers),
            todays_action=ActionDTO(action.title, action.detail, action.impact),
            suggested_questions=mentor.suggested_questions(profile, matches),
        )
        return ServiceResult.ok(dto)

    def recommend(self, student_id: StudentId) -> ServiceResult[RecommendationsDTO]:
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No intelligence profile yet.")
        matches = self._matches(profile)
        cards = tuple(self._card(profile, m) for m in matches)
        return ServiceResult.ok(RecommendationsDTO(student_id.value, cards))

    def career_detail(self, student_id: StudentId, career_id: str
                      ) -> ServiceResult[CareerDetailDTO]:
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No intelligence profile yet.")
        insight = self._insights.get(career_id)
        match = next((m for m in self._matches(profile) if m.career_id == career_id), None)
        if insight is None or match is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Career not found.")
        if self._memory is not None:
            self._memory.set_goal(student_id, match.name)
        first_skill = insight.roadmap[0].name if insight.roadmap else "a key skill"
        top = profile.top_strengths(1)
        note = (
            f"You already possess strong {top[0].name.lower()}. Adding {first_skill} "
            f"would significantly increase your compatibility with {match.name}."
            if top else
            f"Building {first_skill} would increase your compatibility with {match.name}."
        )
        rm = mentor.roadmap(insight, match.name)
        dto = CareerDetailDTO(
            career_id=career_id, name=match.name, compatibility=match.score,
            overview=insight.summary, personal_note=note,
            daily_work=insight.daily_work, responsibilities=insight.responsibilities,
            progression=insight.progression,
            salary_range=_salary_range(insight),
            required_education=insight.required_education, certifications=insight.certifications,
            demand=_band(insight.demand), future_outlook=_band(insight.growth),
            automation_risk=_risk_band(insight.automation_risk),
            remote_compatibility=_band(insight.remote_compatibility),
            related_careers=tuple(self._name(c) for c in insight.related_careers),
            roadmap=_roadmap_dto(career_id, rm),
        )
        return ServiceResult.ok(dto)

    def roadmap(self, student_id: StudentId, career_id: str) -> ServiceResult[RoadmapDTO]:
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No intelligence profile yet.")
        insight = self._insights.get(career_id)
        if insight is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Career not found.")
        name = self._name(career_id)
        if self._memory is not None:
            self._memory.set_goal(student_id, name)
        return ServiceResult.ok(_roadmap_dto(career_id, mentor.roadmap(insight, name)))

    def skill_gap(self, student_id: StudentId, career_id: str) -> ServiceResult[SkillGapDTO]:
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No intelligence profile yet.")
        match = next((m for m in self._matches(profile) if m.career_id == career_id), None)
        if match is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Career not found.")
        gap = mentor.skill_gap(profile, match, self._insights.get(career_id))
        dto = SkillGapDTO(
            career_id=career_id, name=match.name,
            current_compatibility=gap.current_compatibility,
            projected_compatibility=gap.projected_compatibility,
            strengths=gap.strengths,
            missing=tuple(MissingSkillDTO(m.name, m.importance, m.weeks, m.employability_gain)
                          for m in gap.missing),
        )
        return ServiceResult.ok(dto)

    def compare(self, student_id: StudentId, career_a: str, career_b: str
                ) -> ServiceResult[ComparisonDTO]:
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No intelligence profile yet.")
        ia, ib = self._insights.get(career_a), self._insights.get(career_b)
        matches = self._matches(profile)
        ma = next((m for m in matches if m.career_id == career_a), None)
        mb = next((m for m in matches if m.career_id == career_b), None)
        if not (ia and ib and ma and mb):
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Careers not found.")
        cmp = mentor.compare(profile, ma.name, ia, ma, mb.name, ib, mb)
        dto = ComparisonDTO(
            career_a=cmp.career_a, career_b=cmp.career_b,
            rows=tuple(ComparisonRowDTO(r.dimension, r.a, r.b, r.winner) for r in cmp.rows),
            recommendation=cmp.recommendation,
        )
        return ServiceResult.ok(dto)

    def coach(self, student_id: StudentId, message: str, grounded: str
              ) -> ServiceResult[CoachReplyDTO]:
        """Compose a context-aware, mentor-style reply (Epic 4). ``grounded`` is the
        agent's retrieval-grounded answer; the mentor personalizes around it."""
        profile = self._profile_or_none(student_id)
        if profile is None:
            return ServiceResult.ok(CoachReplyDTO(
                grounded or "Tell me about your interests and I'll guide you.", ()))
        matches = self._matches(profile)
        reply = mentor.coach_reply(profile, matches, message, grounded)
        return ServiceResult.ok(CoachReplyDTO(
            reply, mentor.suggested_questions(profile, matches)))

    def report_html(self, student_id: StudentId) -> ServiceResult[str]:
        dash = self.dashboard(student_id)
        recs = self.recommend(student_id)
        if not dash.success or not recs.success:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No profile to report on.")
        return ServiceResult.ok(_render_report(dash.data, recs.data))

    # -- assembly ----------------------------------------------------------

    def _card(self, profile: StudentIntelligenceProfile, match: CareerRecommendation
              ) -> PremiumCardDTO:
        insight = self._insights.get(match.career_id)
        gap = mentor.skill_gap(profile, match, insight)
        challenges: list[str] = []
        if profile.weaknesses:
            challenges.append(f"May require developing {profile.weaknesses[0].name.lower()}")
        if insight and insight.automation_risk >= 0.3:
            challenges.append("Some routine tasks may be automated over time")
        if not challenges:
            challenges.append("Maintaining skills as the field evolves")
        skill_gaps = tuple(m.name for m in gap.missing)
        next_actions = [f"Start learning {skill_gaps[0]}"] if skill_gaps else ["Build a portfolio project"]
        next_actions.append("Add a portfolio project to demonstrate ability")
        return PremiumCardDTO(
            career_id=match.career_id, name=match.name, score=match.score,
            confidence=match.confidence,
            summary=insight.summary if insight else "",
            match_explanation=match.reasons,
            strengths_used=match.top_strengths,
            challenges=tuple(challenges),
            required_education=insight.required_education if insight else (),
            salary_range=_salary_range(insight) if insight else "—",
            future_demand=_band(insight.demand) if insight else "—",
            automation_risk=_risk_band(insight.automation_risk) if insight else "—",
            remote_compatibility=_band(insight.remote_compatibility) if insight else "—",
            skill_gaps=skill_gaps,
            estimated_learning_weeks=sum(m.weeks for m in gap.missing),
            next_actions=tuple(next_actions),
            alternatives=tuple(self._name(c) for c in (insight.related_careers if insight else ())),
            evidence=tuple(EvidenceDTO(e.claim, e.source, e.detail, round(e.confidence, 3))
                           for e in match.evidence),
        )

    def _greeting(self, student_id: StudentId) -> str:
        if self._memory is None:
            return ""
        hist = self._memory.readiness_history(student_id)
        goal = self._memory.goal(student_id)
        if len(hist) >= 2:
            prev, cur = hist[-2], hist[-1]
            parts = ["Welcome back."]
            if goal:
                parts.append(f"Last time you were exploring {goal}.")
            if cur != prev:
                parts.append(f"Your readiness moved from {prev}% to {cur}%.")
            parts.append("Let's keep building momentum.")
            return " ".join(parts)
        if goal:
            return f"Welcome back. You were exploring {goal} — let's continue."
        return ""


# -- module-level mappers --------------------------------------------------


def _summary_dto(student_id: str, profile: StudentIntelligenceProfile) -> IntelligenceSummaryDTO:
    return IntelligenceSummaryDTO(
        student_id=student_id,
        confidence=round(profile.confidence, 3),
        learning_style=profile.learning_style.value,
        preferred_work_environment=profile.preferred_work_environment.value,
        top_strengths=tuple(t.name for t in profile.top_strengths(3)),
        top_interests=tuple(t.name for t in profile.top_interests(3)),
    )


def _roadmap_dto(career_id: str, rm: mentor.Roadmap) -> RoadmapDTO:
    return RoadmapDTO(
        career_id=career_id, goal=rm.goal,
        steps=tuple(RoadmapStepDTO(s.title, s.duration, s.difficulty, s.importance,
                                   s.resources, s.status) for s in rm.steps),
    )


def _render_report(dash: DashboardDTO, recs: RecommendationsDTO) -> str:
    """A premium, self-contained HTML report (Epic 9)."""
    strengths = "".join(f"<li><b>{s.title}</b> ({s.confidence}%) — {s.explanation}</li>"
                        for s in dash.strengths)
    cards = "".join(
        f"<div class='r'><h3>{c.name} — {round(c.score)}%</h3>"
        f"<p>{c.summary}</p>"
        f"<p><b>Why:</b> {'; '.join(c.match_explanation)}</p>"
        f"<p><b>Salary:</b> {c.salary_range} &nbsp; <b>Demand:</b> {c.future_demand} &nbsp; "
        f"<b>Automation risk:</b> {c.automation_risk}</p>"
        f"<p><b>Skill gaps:</b> {', '.join(c.skill_gaps) or 'None'}</p></div>"
        for c in recs.cards
    )
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>AI Career Report</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:820px;margin:40px auto;color:#1b2330;line-height:1.6;padding:0 20px}}
h1{{border-bottom:3px solid #3b5bdb;padding-bottom:8px}}
h2{{color:#3b5bdb;margin-top:32px}}
.r{{border:1px solid #d8dee9;border-radius:10px;padding:14px 18px;margin:12px 0}}
.badge{{display:inline-block;background:#3b5bdb;color:#fff;border-radius:999px;padding:4px 14px;font-weight:700}}
</style></head><body>
<h1>AI Career Report</h1>
<p class='badge'>Career Readiness {dash.readiness.score}% · {dash.readiness.level}</p>
<h2>Executive Summary</h2><p>{dash.ai_summary}</p>
<h2>Strength Analysis</h2><ul>{strengths}</ul>
<h2>Learning Style</h2><p>{dash.learning_style.style.title()} — {dash.learning_style.explanation}</p>
<h2>Biggest Opportunity</h2><p>{dash.opportunity.title}: {dash.opportunity.detail}
(+{dash.opportunity.employability_gain}% employability)</p>
<h2>Top Careers</h2>{cards}
<h2>Personal Advice</h2><p>{dash.todays_action.title}. {dash.todays_action.detail}</p>
<hr><p style='color:#5c6675'>Generated by Detective Monkey — guidance, not prediction.</p>
</body></html>"""
