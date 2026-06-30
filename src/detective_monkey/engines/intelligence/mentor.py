"""Mentor reasoning — premium, personalized derivations.

Extends the single reasoning component (no new layer) with deterministic,
profile-driven outputs the UX phase needs: career readiness, a personalized AI
summary, the biggest opportunity, today's action, skill-gap analysis, roadmaps,
comparisons, suggested questions and premium recommendation cards.

Everything is derived from the :class:`StudentIntelligenceProfile` + per-career
:class:`CareerInsight` data, so every output is unique to the student without
requiring an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import StudentIntelligenceProfile
from .ranker import CareerRecommendation


# --------------------------------------------------------------------------
# Career data (supplied by the seed; not architecture)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RoadmapSkill:
    name: str
    weeks: int
    difficulty: str          # easy / moderate / hard
    employability_gain: int  # percentage points


@dataclass(frozen=True, slots=True)
class CareerInsight:
    """Premium career metadata used by cards, detail, roadmap and comparison."""

    career_id: str
    summary: str
    daily_work: tuple[str, ...]
    responsibilities: tuple[str, ...]
    progression: tuple[tuple[str, str], ...]   # (title, typical timeframe)
    salary_entry: int
    salary_senior: int
    currency: str
    demand: float                # 0-1
    growth: float                # 0-1
    automation_risk: float       # 0-1
    remote_compatibility: float  # 0-1
    required_education: tuple[str, ...]
    certifications: tuple[str, ...]
    related_careers: tuple[str, ...]
    roadmap: tuple[RoadmapSkill, ...]


# --------------------------------------------------------------------------
# View value objects
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Readiness:
    score: int
    level: str
    explanation: str
    increases: tuple[str, ...]
    decreases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Opportunity:
    title: str
    detail: str
    employability_gain: int
    extra_careers: int


@dataclass(frozen=True, slots=True)
class DailyAction:
    title: str
    detail: str
    impact: str


@dataclass(frozen=True, slots=True)
class StrengthView:
    title: str
    confidence: int
    explanation: str


@dataclass(frozen=True, slots=True)
class MissingSkill:
    name: str
    importance: str
    weeks: int
    employability_gain: int


@dataclass(frozen=True, slots=True)
class SkillGapAnalysis:
    current_compatibility: int
    projected_compatibility: int
    strengths: tuple[str, ...]
    missing: tuple[MissingSkill, ...]


@dataclass(frozen=True, slots=True)
class RoadmapStep:
    title: str
    duration: str
    difficulty: str
    importance: str
    resources: tuple[str, ...]
    status: str  # not_started / in_progress / complete


@dataclass(frozen=True, slots=True)
class Roadmap:
    goal: str
    steps: tuple[RoadmapStep, ...]


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    dimension: str
    a: str
    b: str
    winner: str  # "a" / "b" / "tie"


@dataclass(frozen=True, slots=True)
class Comparison:
    career_a: str
    career_b: str
    rows: tuple[ComparisonRow, ...]
    recommendation: str


# --------------------------------------------------------------------------
# Derivations
# --------------------------------------------------------------------------

_READINESS_LEVELS = (
    (85, "Excellent"), (70, "Strong"), (55, "Developing"), (0, "Emerging"),
)


def _level(score: int) -> str:
    for threshold, label in _READINESS_LEVELS:
        if score >= threshold:
            return label
    return "Emerging"


def career_readiness(profile: StudentIntelligenceProfile) -> Readiness:
    strengths_avg = (
        sum(t.score for t in profile.strengths) / len(profile.strengths)
        if profile.strengths else 0.5
    )
    breadth = (
        sum(v for _, v in profile.skill_vector.components) / len(profile.skill_vector.components)
        if profile.skill_vector.components else 0.5
    )
    score = round(100 * (0.4 * profile.confidence + 0.4 * strengths_avg + 0.2 * breadth))
    score = max(0, min(100, score))
    top = profile.top_strengths(1)
    explanation = (
        f"Your readiness reflects strong {top[0].name.lower()} and an assessment "
        f"confidence of {round(profile.confidence * 100)}%."
        if top else "Complete more of your assessment to raise this score."
    )
    increases = [f"Strengthen {w.name.lower()}" for w in profile.weaknesses[:2]]
    increases.append("Add an in-demand technical skill (e.g. SQL)")
    decreases = []
    if profile.confidence < 0.7:
        decreases.append("Incomplete or inconsistent assessment answers")
    if profile.weaknesses:
        decreases.append(f"Gaps in {profile.weaknesses[0].name.lower()}")
    if not decreases:
        decreases.append("Letting skills go stale without practice")
    return Readiness(score, _level(score), explanation, tuple(increases), tuple(decreases))


def ai_summary(
    profile: StudentIntelligenceProfile,
    matches: tuple[CareerRecommendation, ...],
    opportunity: Opportunity,
) -> str:
    strengths = profile.top_strengths(2)
    s_text = (
        " and ".join(t.name.lower() for t in strengths) if strengths
        else "a developing profile"
    )
    top_two = [m.name for m in matches[:2]]
    careers = " and ".join(top_two) if top_two else "several promising fields"
    return (
        f"Based on your assessment, you show exceptional {s_text}. "
        f"Your profile currently aligns most strongly with {careers}. "
        f"Your biggest opportunity right now is {opportunity.title.lower()}, "
        f"estimated to improve employability by about {opportunity.employability_gain}% "
        f"and open {opportunity.extra_careers} additional career matches."
    )


def biggest_opportunity(
    matches: tuple[CareerRecommendation, ...],
    insights: dict[str, CareerInsight],
) -> Opportunity:
    # Most common first roadmap skill across the top matches = highest leverage.
    counts: dict[str, tuple[int, RoadmapSkill]] = {}
    for m in matches[:5]:
        insight = insights.get(m.career_id)
        if insight and insight.roadmap:
            skill = insight.roadmap[0]
            count, _ = counts.get(skill.name, (0, skill))
            counts[skill.name] = (count + 1, skill)
    if not counts:
        return Opportunity("Building a portfolio project",
                           "A portfolio demonstrates real ability to employers.", 5, 2)
    name, (count, skill) = max(counts.items(), key=lambda kv: kv[1][0])
    return Opportunity(
        title=f"Learning {name}",
        detail=f"{name} is the single highest-impact skill across your top matches.",
        employability_gain=skill.employability_gain,
        extra_careers=count + 1,
    )


def todays_recommendation(
    profile: StudentIntelligenceProfile, opportunity: Opportunity
) -> DailyAction:
    skill = opportunity.title.replace("Learning ", "")
    style = profile.learning_style.value
    verb = {
        "analytical": "study the core theory of",
        "practical": "build a small hands-on project using",
        "exploratory": "explore an interactive tutorial on",
        "collaborative": "join a study group focused on",
        "reflective": "read and take notes on",
    }.get(style, "spend one focused hour on")
    return DailyAction(
        title=f"Spend one hour to {verb} {skill}",
        detail=f"Matched to your {style} learning style — the highest predicted impact today.",
        impact="High",
    )


_SKILL_TITLES = {
    "problem_solving": "Problem Solving",
    "communication": "Communication",
    "creativity": "Creativity",
    "leadership": "Leadership",
    "technical": "Technical Aptitude",
    "collaboration": "Collaboration",
    "discipline": "Discipline",
    "learning_agility": "Learning Agility",
}


def strength_views(profile: StudentIntelligenceProfile, n: int = 5) -> tuple[StrengthView, ...]:
    """Always returns the student's top ``n`` strengths (Epic 1 displays 5),
    drawn from the always-present skill vector so the dashboard is never empty."""
    top = profile.skill_vector.top(n)
    out = []
    for key, value in top:
        conf = round(value * 100)
        qualifier = "a clear strength" if value >= 0.66 else (
            "a developing strength" if value >= 0.45 else "an emerging area")
        out.append(StrengthView(
            title=_SKILL_TITLES.get(key, key.replace("_", " ").title()),
            confidence=conf,
            explanation=f"Scored {conf}% in your assessment — {qualifier}.",
        ))
    return tuple(out)


def skill_gap(
    profile: StudentIntelligenceProfile,
    match: CareerRecommendation,
    insight: CareerInsight | None,
) -> SkillGapAnalysis:
    current = round(match.score)
    technical = profile.skill_vector.get("technical", 0.5)
    missing: list[MissingSkill] = []
    gain_total = 0
    if insight:
        for i, rs in enumerate(insight.roadmap):
            # Assume foundational skills are partly covered when technical is high.
            if i == 0 and technical >= 0.7:
                continue
            missing.append(MissingSkill(rs.name, _importance_label(rs), rs.weeks,
                                        rs.employability_gain))
            gain_total += rs.employability_gain
    projected = min(99, current + gain_total)
    return SkillGapAnalysis(
        current_compatibility=current,
        projected_compatibility=projected,
        strengths=match.top_strengths,
        missing=tuple(missing),
    )


def _importance_label(rs: RoadmapSkill) -> str:
    return "Critical" if rs.employability_gain >= 6 else ("High" if rs.employability_gain >= 4 else "Medium")


def roadmap(insight: CareerInsight, name: str) -> Roadmap:
    steps: list[RoadmapStep] = []
    for i, rs in enumerate(insight.roadmap):
        steps.append(RoadmapStep(
            title=rs.name,
            duration=f"~{rs.weeks} weeks",
            difficulty=rs.difficulty,
            importance=_importance_label(rs),
            resources=(f"Recommended course on {rs.name}", f"Practice project: {rs.name}"),
            status="in_progress" if i == 0 else "not_started",
        ))
    # Universal closing milestones.
    steps.append(RoadmapStep("Portfolio", "~3 weeks", "moderate", "High",
                             ("Publish 2-3 projects",), "not_started"))
    steps.append(RoadmapStep("Internship / first role", "ongoing", "hard", "Critical",
                             ("Apply to internships",), "not_started"))
    return Roadmap(goal=f"Become {name}", steps=tuple(steps))


def compare(
    profile: StudentIntelligenceProfile,
    name_a: str, insight_a: CareerInsight, match_a: CareerRecommendation,
    name_b: str, insight_b: CareerInsight, match_b: CareerRecommendation,
) -> Comparison:
    def money(i: CareerInsight) -> str:
        return f"{i.currency}{i.salary_entry:,}–{i.salary_senior:,}"

    def pct(v: float) -> str:
        return f"{round(v * 100)}%"

    rows = (
        ComparisonRow("Salary range", money(insight_a), money(insight_b),
                      _winner(insight_a.salary_senior, insight_b.salary_senior)),
        ComparisonRow("Market demand", pct(insight_a.demand), pct(insight_b.demand),
                      _winner(insight_a.demand, insight_b.demand)),
        ComparisonRow("Growth", pct(insight_a.growth), pct(insight_b.growth),
                      _winner(insight_a.growth, insight_b.growth)),
        ComparisonRow("Education", insight_a.required_education[0] if insight_a.required_education else "—",
                      insight_b.required_education[0] if insight_b.required_education else "—", "tie"),
        ComparisonRow("Remote-friendly", pct(insight_a.remote_compatibility),
                      pct(insight_b.remote_compatibility),
                      _winner(insight_a.remote_compatibility, insight_b.remote_compatibility)),
        ComparisonRow("AI automation risk", pct(insight_a.automation_risk),
                      pct(insight_b.automation_risk),
                      _winner(insight_b.automation_risk, insight_a.automation_risk)),  # lower is better
        ComparisonRow("Personal compatibility", f"{round(match_a.score)}%",
                      f"{round(match_b.score)}%", _winner(match_a.score, match_b.score)),
    )
    if match_a.score >= match_b.score:
        rec = (f"{name_a} is the stronger personal match ({round(match_a.score)}% vs "
               f"{round(match_b.score)}%), aligning better with your strengths.")
    else:
        rec = (f"{name_b} is the stronger personal match ({round(match_b.score)}% vs "
               f"{round(match_a.score)}%), aligning better with your strengths.")
    return Comparison(name_a, name_b, rows, rec)


def _winner(a: float, b: float) -> str:
    if abs(a - b) < 1e-9:
        return "tie"
    return "a" if a > b else "b"


_TRACKED_SKILLS = ("python", "sql", "statistics", "machine learning", "communication", "design")


def coach_reply(
    profile: StudentIntelligenceProfile,
    matches: tuple[CareerRecommendation, ...],
    message: str,
    grounded: str,
) -> str:
    """Compose a personal, mentor-style reply (Epic 4) from the profile + grounded
    retrieval text — guides rather than just answering."""
    style = profile.learning_style.value
    strengths = profile.top_strengths(1)
    s = strengths[0].name.lower() if strengths else "your strengths"
    intro = f"Given your {style} learning style and strong {s}, here's my guidance. "

    msg = message.lower()
    for skill in _TRACKED_SKILLS:
        if skill in msg:
            intro += (
                f"{skill.title()} is a high-leverage skill across your recommended "
                f"careers — based on your {style} style, project-based practice would "
                f"get you to employable proficiency in roughly 12 weeks. ")
            break

    if grounded and "couldn't find" not in grounded.lower():
        body = grounded
    elif matches:
        body = "Your strongest matches right now are " + ", ".join(m.name for m in matches[:2]) + "."
    else:
        body = "Tell me a little about what you enjoy and I'll point you in the right direction."

    return f"{intro}\n\n{body}\n\nWant me to build a roadmap or compare your top careers?"


def suggested_questions(
    profile: StudentIntelligenceProfile,
    matches: tuple[CareerRecommendation, ...],
) -> tuple[str, ...]:
    top = matches[0].name if matches else "my top career"
    questions = [
        "How can I increase my readiness score?",
        f"Build me a roadmap to become a {top}",
        "Compare my top two careers",
        "What should I study next?",
        "Show me AI-safe careers",
    ]
    if matches and matches[0].missing_information:
        questions.insert(1, f"What skills am I missing for {top}?")
    if profile.confidence < 0.6:
        questions.append("Why is my confidence low?")
    return tuple(questions[:6])
