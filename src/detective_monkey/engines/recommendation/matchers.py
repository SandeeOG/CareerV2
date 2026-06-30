"""Independent match engines (25_RECOMMENDATION_ENGINE.md §3, §6–§12).

The Recommendation Engine owns orchestration; these matchers own scoring (25 §1).
Each is independent (INV-03), deterministic, and produces a score + confidence +
evidence (§6, INV-02). A matcher returns ``None`` when it has no applicable data,
so its weight is redistributed rather than fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ...domain.career.career import Career
from ...domain.common.confidence import Confidence
from ...domain.common.scores import Importance, ProficiencyLevel, Score
from ...domain.education.enums import RequirementType
from ...domain.education.student_education import EducationGap, StudentEducation
from ...domain.labour_market.snapshot import LabourMarketSnapshot
from ...domain.recommendation.dimensions import Dimension
from ...domain.recommendation.evidence import EvidenceCategory, RecommendationEvidence
from ...domain.skills.skill_gap import SkillGap
from ...domain.skills.student_skill import StudentSkill
from ...domain.student.goals import StudentGoals
from ...domain.student.profile import StudentIntelligenceProfile

_IMPORTANCE_WEIGHT = {
    Importance.CRITICAL: 1.0,
    Importance.HIGH: 0.8,
    Importance.MEDIUM: 0.5,
    Importance.LOW: 0.3,
    Importance.TEMPORARY: 0.1,
}


def importance_weight(importance: Importance | None) -> float:
    return _IMPORTANCE_WEIGHT.get(importance, 0.5) if importance else 0.5


@dataclass(frozen=True, slots=True)
class MatchContext:
    """Everything a matcher needs for one (student, career) pair."""

    profile: StudentIntelligenceProfile
    career: Career
    student_skills: dict[str, StudentSkill] = field(default_factory=dict)
    student_education: tuple[StudentEducation, ...] = field(default_factory=tuple)
    goals: StudentGoals | None = None
    labour: LabourMarketSnapshot | None = None


@dataclass(frozen=True, slots=True)
class MatchResult:
    """A matcher's output for one dimension."""

    dimension: Dimension
    score: Score
    confidence: Confidence
    evidence: tuple[RecommendationEvidence, ...] = field(default_factory=tuple)
    skill_gaps: tuple[SkillGap, ...] = field(default_factory=tuple)
    education_gaps: tuple[EducationGap, ...] = field(default_factory=tuple)


@runtime_checkable
class MatchEngine(Protocol):
    """Contract every match engine implements (25 §3)."""

    @property
    def dimension(self) -> Dimension: ...

    def match(self, ctx: MatchContext) -> MatchResult | None: ...


# --------------------------------------------------------------------------
# Concrete deterministic matchers
# --------------------------------------------------------------------------


class PsychologicalMatcher:
    """Compares career personality requirements to student constructs (25 §6)."""

    dimension = Dimension.PSYCHOLOGICAL

    def match(self, ctx: MatchContext) -> MatchResult | None:
        reqs = ctx.career.personality
        if not reqs:
            return None
        weighted_total = 0.0
        weight_sum = 0.0
        confidences: list[float] = []
        sources = []
        present = 0
        for req in reqs:
            cs = ctx.profile.construct(req.construct)
            if cs is None:
                continue
            present += 1
            if req.optimal_range.contains(cs.score):
                fit = 100.0
            else:
                low, high = req.optimal_range.low.value, req.optimal_range.high.value
                distance = (low - cs.score.value) if cs.score.value < low else (
                    cs.score.value - high
                )
                fit = max(0.0, 100.0 - distance)
            w = importance_weight(req.importance)
            weighted_total += fit * w
            weight_sum += w
            confidences.append(cs.confidence.value.value)
            sources.extend(cs.evidence)
        if present == 0 or weight_sum == 0:
            return None
        score = weighted_total / weight_sum
        coverage = present / len(reqs)
        conf = (sum(confidences) / len(confidences)) * coverage
        ev = RecommendationEvidence(
            category=EvidenceCategory.BEHAVIOURAL_ALIGNMENT,
            summary=f"Personality fit across {present}/{len(reqs)} constructs.",
            dimension=self.dimension,
            sources=tuple(sources),
        )
        return MatchResult(self.dimension, Score(score), Confidence.of(conf), (ev,))


class SkillMatcher:
    """Compares student skills to career skill requirements (25 §7)."""

    dimension = Dimension.SKILL

    def match(self, ctx: MatchContext) -> MatchResult | None:
        reqs = ctx.career.skills
        if not reqs:
            return None
        weighted_total = 0.0
        weight_sum = 0.0
        have_data = 0
        gaps: list[SkillGap] = []
        for cs in reqs:
            student = ctx.student_skills.get(cs.skill_id.value)
            current = student.proficiency if student else ProficiencyLevel.NO_EVIDENCE
            if student is not None:
                have_data += 1
            required = cs.recommended_proficiency.value or 1
            ratio = min(1.0, current.value / required) if required else 1.0
            w = importance_weight(cs.importance)
            weighted_total += ratio * 100.0 * w
            weight_sum += w
            gap = SkillGap(cs.skill_id, cs.recommended_proficiency, current)
            if not gap.is_met:
                gaps.append(gap)
        if weight_sum == 0:
            return None
        score = weighted_total / weight_sum
        coverage = have_data / len(reqs)
        conf = 0.3 + 0.7 * coverage  # more student data => more confident
        ev = RecommendationEvidence(
            category=EvidenceCategory.SKILL_ALIGNMENT,
            summary=f"Skill coverage with {len(gaps)} gap(s) across {len(reqs)} skills.",
            dimension=self.dimension,
        )
        return MatchResult(
            self.dimension, Score(score), Confidence.of(conf), (ev,), tuple(gaps)
        )


class _NameMatchMixin:
    """Shared helper: look up a profile score by a knowledge/competency name."""

    @staticmethod
    def _profile_score(profile: StudentIntelligenceProfile, name: str) -> float | None:
        key = name.strip().lower()
        for cs in profile.construct_scores:
            if cs.construct.lower() == key:
                return cs.score.value
        for ds in profile.domain_scores:
            if ds.domain.lower() == key:
                return ds.score.value
        for df in profile.derived_features:
            if df.name.lower() == key:
                return df.score.value
        return None


class KnowledgeMatcher(_NameMatchMixin):
    """Approximates knowledge alignment via profile signals by name (25 §8)."""

    dimension = Dimension.KNOWLEDGE

    def match(self, ctx: MatchContext) -> MatchResult | None:
        areas = ctx.career.knowledge_areas
        if not areas:
            return None
        weighted_total = 0.0
        weight_sum = 0.0
        matched = 0
        for area in areas:
            score = self._profile_score(ctx.profile, area.name)
            w = importance_weight(area.importance)
            if score is not None:
                matched += 1
                weighted_total += score * w
            weight_sum += w
        if weight_sum == 0:
            return None
        coverage = matched / len(areas)
        score = (weighted_total / weight_sum) if matched else 0.0
        conf = 0.2 + 0.6 * coverage  # knowledge is approximated => modest confidence
        ev = RecommendationEvidence(
            category=EvidenceCategory.STRENGTH_ALIGNMENT,
            summary=f"Knowledge alignment across {matched}/{len(areas)} areas.",
            dimension=self.dimension,
        )
        return MatchResult(self.dimension, Score(score), Confidence.of(conf), (ev,))


class CompetencyMatcher(_NameMatchMixin):
    """Approximates competency alignment via profile signals by name (25 §10)."""

    dimension = Dimension.COMPETENCY

    def match(self, ctx: MatchContext) -> MatchResult | None:
        comps = ctx.career.competencies
        if not comps:
            return None
        total = 0.0
        weight_sum = 0.0
        matched = 0
        for comp in comps:
            score = self._profile_score(ctx.profile, comp.name)
            w = importance_weight(comp.importance)
            if score is not None:
                matched += 1
                total += score * w
            weight_sum += w
        if weight_sum == 0:
            return None
        coverage = matched / len(comps)
        score = (total / weight_sum) if matched else 0.0
        conf = 0.2 + 0.6 * coverage
        ev = RecommendationEvidence(
            category=EvidenceCategory.STRENGTH_ALIGNMENT,
            summary=f"Competency alignment across {matched}/{len(comps)} competencies.",
            dimension=self.dimension,
        )
        return MatchResult(self.dimension, Score(score), Confidence.of(conf), (ev,))


class EducationMatcher:
    """Compares student education to career education requirements (25 §9)."""

    dimension = Dimension.EDUCATION

    def match(self, ctx: MatchContext) -> MatchResult | None:
        required = ctx.career.education_pathways
        if not required:
            return None
        completed = {
            se.pathway_id.value
            for se in ctx.student_education
            if se.status.value in ("completed", "in_progress")
        }
        satisfied = [p for p in required if p.value in completed]
        score = (len(satisfied) / len(required)) * 100.0
        gaps = tuple(
            EducationGap(p, RequirementType.RECOMMENDED, satisfied=False)
            for p in required
            if p.value not in completed
        )
        conf = 0.5 if ctx.student_education else 0.3
        ev = RecommendationEvidence(
            category=EvidenceCategory.EDUCATION_ALIGNMENT,
            summary=f"{len(satisfied)}/{len(required)} education pathways satisfied.",
            dimension=self.dimension,
        )
        return MatchResult(
            self.dimension, Score(score), Confidence.of(conf), (ev,), education_gaps=gaps
        )


class GoalMatcher:
    """Evaluates alignment with explicit student goals (25 §11).

    Goals influence recommendations without dominating them: this matcher centres
    on a neutral 50 and adjusts based on overlap.
    """

    dimension = Dimension.GOAL

    def match(self, ctx: MatchContext) -> MatchResult | None:
        goals = ctx.goals
        if goals is None:
            return None
        career_name = ctx.career.identity.canonical_name.lower()
        signals = 0.0
        considered = 0
        if goals.dream_careers:
            considered += 1
            if any(career_name == d.lower() for d in goals.dream_careers):
                signals += 1.0
        if goals.work_preferences and ctx.career.work_styles:
            considered += 1
            styles = {ws.name.lower() for ws in ctx.career.work_styles}
            prefs = {p.lower() for p in goals.work_preferences}
            if styles & prefs:
                signals += len(styles & prefs) / len(prefs)
        if considered == 0:
            return None
        score = max(0.0, min(100.0, 50.0 + 50.0 * (signals / considered)))
        ev = RecommendationEvidence(
            category=EvidenceCategory.GOAL_ALIGNMENT,
            summary="Alignment with declared goals and preferences.",
            dimension=self.dimension,
        )
        return MatchResult(self.dimension, Score(score), Confidence.of(0.4), (ev,))


class LabourMarketMatcher:
    """Turns labour-market scores into a dimension (25 §12).

    Carries a small weight (per the weight configuration) so it adjusts but never
    dominates student fit (INV-08).
    """

    dimension = Dimension.LABOUR_MARKET

    def match(self, ctx: MatchContext) -> MatchResult | None:
        snap = ctx.labour
        if snap is None:
            return None
        s = snap.scores
        present = [
            v.value
            for v in (
                s.demand_score,
                s.growth_score,
                s.career_stability_score,
                s.ai_opportunity_score,
            )
            if v is not None
        ]
        if not present:
            return None
        score = (sum(present) / len(present)) * 100.0
        conf = 0.3 + 0.5 * (len(present) / 4)
        ev = RecommendationEvidence(
            category=EvidenceCategory.LABOUR_MARKET_ALIGNMENT,
            summary=f"Labour-market context from {snap.period} ({snap.geography.name or 'global'}).",
            dimension=self.dimension,
        )
        return MatchResult(self.dimension, Score(score), Confidence.of(conf), (ev,))


def default_matchers() -> tuple[MatchEngine, ...]:
    """The standard set of match engines (25 §4 pipeline order)."""
    return (
        PsychologicalMatcher(),
        SkillMatcher(),
        KnowledgeMatcher(),
        EducationMatcher(),
        CompetencyMatcher(),
        GoalMatcher(),
        LabourMarketMatcher(),
    )
