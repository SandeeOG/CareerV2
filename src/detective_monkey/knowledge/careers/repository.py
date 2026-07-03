"""CareerKnowledgeRepository — the application's single source of career truth.

Every consumer — Recommendation Engine, Intelligence mentor surfaces, Career
Discovery, AI Coach, Reports, the Explore Careers UI — reads career
information from this repository, which is built exclusively from the
validated, generated JSON knowledge files. No hardcoded career dictionaries
exist anywhere else.

The repository also *adapts* profiles into the two shapes the existing
architecture already consumes (39: "reuse the current services"): `Career`
aggregates for the ranker and `CareerInsight` objects for the mentor — so
recommendation, roadmap, skill-gap, comparison and report features run over
all ~300 knowledge careers without any engine changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.career.career import Career
from ...domain.career.identity import CareerIdentity
from ...domain.career.layers import PersonalityRequirement
from ...domain.common.identifiers import CareerId, SkillId
from ...domain.common.scores import Importance, ProficiencyLevel, Score, ScoreRange
from ...domain.common.versioning import Version
from ...domain.skills.career_skill import CareerSkill
from ..normalizers.text import slugify, tokens
from .loader import LoadReport  # noqa: TC001 - runtime dataclass reference
from .schema import CareerProfile, IndustryProfile

_V1 = Version(1, "knowledge-v1")

# tag -> assessment construct for personality requirements (first hit CRITICAL,
# second HIGH). Same construct vocabulary the Assessment Engine measures.
_TAG_CONSTRUCTS: tuple[tuple[str, str], ...] = (
    ("analytical", "analytical_thinking"), ("logic", "analytical_thinking"),
    ("mathematics", "analytical_thinking"), ("numbers", "analytical_thinking"),
    ("data", "analytical_thinking"), ("research", "curiosity"),
    ("curious", "curiosity"), ("science", "curiosity"),
    ("creative", "creativity"), ("creativity", "creativity"),
    ("design", "creativity"), ("storytelling", "creativity"),
    ("leadership", "leadership"), ("strategy", "leadership"),
    ("people", "communication"), ("communication", "communication"),
    ("empathy", "communication"), ("teaching", "communication"),
    ("service", "communication"), ("listening", "communication"),
    ("detail", "conscientiousness"), ("discipline", "conscientiousness"),
    ("precision", "conscientiousness"), ("organization", "conscientiousness"),
)

_DIFFICULTY_LABEL = {1: "easy", 2: "easy", 3: "moderate", 4: "hard", 5: "hard"}


@dataclass(frozen=True, slots=True)
class CareerSearchFilters:
    """Structured filters for Explore Careers (38 §Filters)."""

    industry: str = ""
    max_difficulty: int = 0            # 0 = no limit
    max_competition: int = 0
    min_salary_lpa: int = 0            # senior-level ceiling filter
    min_demand: float = 0.0
    remote: bool = False               # remote_work >= 0.6
    ai_safe: bool = False              # automation_risk <= 0.3
    government: bool = False           # government_opportunities >= 0.6
    freelancing: bool = False
    entrepreneurship: bool = False
    education_keyword: str = ""        # matches degrees/alternatives
    country: str = ""
    requires_programming: bool | None = None
    requires_mathematics: bool | None = None
    creativity: bool = False
    leadership: bool = False
    travel_or_outdoor: bool = False
    people_facing: bool = False


class CareerKnowledgeRepository:
    """Read-only access to the loaded, validated career knowledge base."""

    def __init__(
        self,
        profiles: tuple[CareerProfile, ...],
        industries: tuple[IndustryProfile, ...],
        report: LoadReport | None = None,
    ) -> None:
        self._profiles = profiles
        self._industries = industries
        self._report = report
        self._by_id = {p.id: p for p in profiles}
        self._by_name = {p.name: p for p in profiles}
        self._by_industry: dict[str, list[CareerProfile]] = {}
        for p in profiles:
            self._by_industry.setdefault(p.industry, []).append(p)

    # -- basic access ---------------------------------------------------------

    @property
    def report(self) -> LoadReport | None:
        return self._report

    def count(self) -> int:
        return len(self._profiles)

    def all_profiles(self) -> tuple[CareerProfile, ...]:
        return self._profiles

    def industries(self) -> tuple[IndustryProfile, ...]:
        return self._industries

    def industry(self, industry_id: str) -> IndustryProfile | None:
        return next((i for i in self._industries if i.id == industry_id), None)

    def careers_in(self, industry_id: str) -> tuple[CareerProfile, ...]:
        return tuple(self._by_industry.get(industry_id, ()))

    def get(self, career_id: str) -> CareerProfile | None:
        return self._by_id.get(career_id) or self._by_name.get(career_id)

    def related(self, career_id: str) -> tuple[CareerProfile, ...]:
        profile = self.get(career_id)
        if profile is None:
            return ()
        found = (self._by_name.get(name) for name in profile.related_careers)
        return tuple(p for p in found if p is not None)

    # -- search + filters (38 §Search, §Filters) -------------------------------

    def search(
        self,
        query: str = "",
        filters: CareerSearchFilters | None = None,
        limit: int = 50,
    ) -> tuple[CareerProfile, ...]:
        filters = filters or CareerSearchFilters()
        candidates = [p for p in self._profiles if self._passes(p, filters)]
        if not query.strip():
            return tuple(candidates[:limit])
        query_tokens = tokens(query)
        scored: list[tuple[float, str, CareerProfile]] = []
        for p in candidates:
            # Name matches outrank family matches outrank body matches, so
            # "software" surfaces Software Engineering above its family peers
            # and far above careers that merely use software.
            name_hits = len(query_tokens & tokens(p.name))
            family_hits = len(query_tokens & tokens(p.career_family))
            body = " ".join((
                p.student_summary, " ".join(p.tags),
                " ".join(p.core_skills), " ".join(p.school_subjects),
                " ".join(p.technical_skills), p.work_environment,
            ))
            body_hits = len(query_tokens & tokens(body))
            score = (4 * name_hits + 2 * family_hits + body_hits) / len(query_tokens)
            if score:
                scored.append((score, p.name, p))
        scored.sort(key=lambda s: (-s[0], s[1]))
        return tuple(p for _, _, p in scored[:limit])

    @staticmethod
    def _passes(p: CareerProfile, f: CareerSearchFilters) -> bool:
        def has_any(text_parts: tuple[str, ...], *words: str) -> bool:
            blob = " ".join(text_parts).lower()
            return any(w in blob for w in words)

        if f.industry and p.industry != f.industry:
            return False
        if f.max_difficulty and p.difficulty > f.max_difficulty:
            return False
        if f.max_competition and p.competition_level > f.max_competition:
            return False
        if f.min_salary_lpa and p.salary_senior_lpa < f.min_salary_lpa:
            return False
        if f.min_demand and p.future_demand < f.min_demand:
            return False
        if f.remote and p.remote_work < 0.6:
            return False
        if f.ai_safe and p.automation_risk > 0.3:
            return False
        if f.government and p.government_opportunities < 0.6:
            return False
        if f.freelancing and p.freelancing < 0.6:
            return False
        if f.entrepreneurship and p.entrepreneurship < 0.6:
            return False
        if f.education_keyword and not has_any(
                p.college_degrees + p.alternative_paths, f.education_keyword.lower()):
            return False
        if f.country and not has_any(p.top_countries, f.country.lower()):
            return False
        programming = has_any(p.tags + p.core_skills + p.technical_skills,
                              "programming", "coding", "python", "javascript")
        if f.requires_programming is True and not programming:
            return False
        if f.requires_programming is False and programming:
            return False
        mathematics = has_any(p.school_subjects, "mathematics", "statistics")
        if f.requires_mathematics is True and not mathematics:
            return False
        if f.requires_mathematics is False and mathematics:
            return False
        if f.creativity and not has_any(p.tags, "creative", "creativity", "design", "art"):
            return False
        if f.leadership and not has_any(p.tags, "leadership", "strategy"):
            return False
        if f.travel_or_outdoor and not has_any(
                p.tags, "outdoors", "travel", "adventure", "sea", "field"):
            return False
        if f.people_facing and not has_any(
                p.tags, "people", "communication", "service", "care", "teaching"):
            return False
        return True

    # -- adapters for the existing engines (single source of truth) ------------

    def career_aggregates(self) -> tuple[Career, ...]:
        """Careers as ranker-ready aggregates with personality requirements
        derived from profile tags and skills referencing canonical skill ids."""
        out = []
        for p in self._profiles:
            constructs: list[str] = []
            for tag, construct in _TAG_CONSTRUCTS:
                if tag in p.tags and construct not in constructs:
                    constructs.append(construct)
            personality = tuple(
                PersonalityRequirement(
                    construct,
                    ScoreRange(Score(65 if i == 0 else 55), Score(100)),
                    Importance.CRITICAL if i == 0 else Importance.HIGH,
                )
                for i, construct in enumerate(constructs[:2])
            )
            skills = tuple(
                CareerSkill(CareerId(p.id), SkillId(f"skill_{slugify(s)}"),
                            Importance.HIGH, ProficiencyLevel.INTERMEDIATE,
                            ProficiencyLevel.ADVANCED)
                for s in p.core_skills[:3]
            )
            out.append(Career(
                identity=CareerIdentity(CareerId(p.id), p.name, p.id,
                                        description=p.student_summary),
                version=_V1,
                personality=personality,
                skills=skills,
            ))
        return tuple(out)

    def insights(self) -> dict:
        """Profiles as the mentor's `CareerInsight` shape, keyed by career id."""
        from ...engines.intelligence import CareerInsight, RoadmapSkill

        out: dict[str, CareerInsight] = {}
        for p in self._profiles:
            label = _DIFFICULTY_LABEL[p.difficulty]
            roadmap = tuple(
                RoadmapSkill(skill, weeks=4 + 2 * min(i + p.difficulty // 2, 4),
                             difficulty=label, employability_gain=6 - i)
                for i, skill in enumerate(p.core_skills[:4])
            )
            out[p.id] = CareerInsight(
                career_id=p.id,
                summary=p.student_summary,
                daily_work=p.daily_responsibilities[:3],
                responsibilities=p.core_skills[:3],
                progression=p.career_progression,
                salary_entry=p.salary_entry_lpa,
                salary_senior=p.salary_senior_lpa,
                currency=p.salary_currency,
                demand=p.future_demand,
                growth=p.growth,
                automation_risk=p.automation_risk,
                remote_compatibility=p.remote_work,
                required_education=p.college_degrees + p.alternative_paths[:1],
                certifications=p.certifications,
                related_careers=tuple(
                    slugify(name) for name in p.related_careers
                ),
                roadmap=roadmap,
            )
        return out
