"""The canonical Career Profile schema (38_FOUNDATIONAL_CAREER_KNOWLEDGE_SYSTEM).

Version 1 of Detective Monkey describes ~300 *broad career paths* grouped into
16 foundational industries — breadth and exploration for students under 18,
not exhaustive specialization. Every career profile is one JSON file following
exactly this schema; no field may be omitted, and only validated profiles
enter the Knowledge Platform.

The schema is future-proof for specializations: a later version adds a
``specializations`` list per career without changing any existing field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

SCHEMA_VERSION = 1

# JSON field -> expected python type. Lists are tuples in the dataclass.
# This is the single source of truth for validation; the generator, the
# validator and the loader all derive from it.
_LIST = tuple
_PAIRS = "pairs"  # list of [str, str]


@dataclass(frozen=True, slots=True)
class CareerProfile:
    """One broad career path — the first-class knowledge entity of v1."""

    # Identity
    id: str                       # slug, e.g. "software-engineering"
    name: str
    industry: str                 # industry id, e.g. "technology-computing"
    career_family: str
    tags: tuple[str, ...]

    # Student-facing framing
    student_summary: str          # one sentence, for a 15-year-old
    overview: str
    who_is_this_for: tuple[str, ...]
    who_should_avoid: tuple[str, ...]

    # The work
    daily_responsibilities: tuple[str, ...]
    work_environment: str
    problem_solving_style: str

    # Education
    school_subjects: tuple[str, ...]
    college_degrees: tuple[str, ...]
    alternative_paths: tuple[str, ...]

    # Skills & tools
    core_skills: tuple[str, ...]
    soft_skills: tuple[str, ...]
    technical_skills: tuple[str, ...]
    future_skills: tuple[str, ...]
    tools: tuple[str, ...]
    technologies: tuple[str, ...]

    # Fit
    personality_traits: tuple[str, ...]
    learning_style: str
    difficulty: int               # 1 (accessible) .. 5 (very demanding)
    competition_level: int        # 1 (open) .. 5 (fierce)

    # Path & opportunity
    career_progression: tuple[tuple[str, str], ...]   # (title, timeframe)
    typical_employers: tuple[str, ...]
    entrepreneurship: float       # 0..1
    government_opportunities: float
    remote_work: float
    freelancing: float

    # Money & outlook (India-first; volatile detail comes from Dynamic Knowledge)
    salary_currency: str          # "₹"
    salary_entry_lpa: int         # lakhs per annum, entry level
    salary_senior_lpa: int
    scope: str
    future_demand: float          # 0..1
    growth: float                 # 0..1
    ai_impact: str
    automation_risk: float        # 0..1

    # Honest framing
    advantages: tuple[str, ...]
    challenges: tuple[str, ...]
    misconceptions: tuple[str, ...]

    # Getting started
    portfolio_ideas: tuple[str, ...]
    projects: tuple[str, ...]
    internships: tuple[str, ...]
    certifications: tuple[str, ...]
    scholarships: tuple[str, ...]
    universities: tuple[str, ...]

    # Learning resources
    books: tuple[str, ...]
    courses: tuple[str, ...]
    youtube: tuple[str, ...]
    communities: tuple[str, ...]

    # Indian opportunities
    major_hiring_cities: tuple[str, ...]
    relocation_cities: tuple[str, ...]
    smaller_city_scope: str
    rural_scope: str
    home_state_note: str

    # International opportunities
    top_countries: tuple[str, ...]
    language_requirements: tuple[str, ...]
    visa_difficulty: str          # "low" | "moderate" | "high"

    # Relationships (names of other generated careers — integrity-validated)
    transition_paths: tuple[str, ...]
    related_careers: tuple[str, ...]

    faqs: tuple[tuple[str, str], ...]   # (question, answer)

    # Trust
    confidence: float             # 0..1
    sources: tuple[str, ...]
    schema_version: int = SCHEMA_VERSION
    version: int = 1


@dataclass(frozen=True, slots=True)
class IndustryProfile:
    """One of the 16 foundational industries."""

    id: str
    name: str
    description: str
    icon: str
    featured_careers: tuple[str, ...] = field(default_factory=tuple)   # career ids
    trending_careers: tuple[str, ...] = field(default_factory=tuple)
    future_note: str = ""


# ---------------------------------------------------------------------------
# Validation — only validated profiles enter the Knowledge Platform.
# ---------------------------------------------------------------------------

_STR_LIST_FIELDS = frozenset(
    f.name for f in fields(CareerProfile)
    if f.type == "tuple[str, ...]"
)
_PAIR_FIELDS = frozenset({"career_progression", "faqs"})
_FLOAT_FIELDS = frozenset({
    "entrepreneurship", "government_opportunities", "remote_work", "freelancing",
    "future_demand", "growth", "automation_risk", "confidence",
})
_INT_FIELDS = frozenset({
    "difficulty", "competition_level", "salary_entry_lpa", "salary_senior_lpa",
    "schema_version", "version",
})
_SCALE_FIELDS = frozenset({"difficulty", "competition_level"})

REQUIRED_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(CareerProfile))


def validate_career_json(data: object) -> list[str]:
    """Return a list of problems; an empty list means the profile is valid.

    Checks (38 §Validation): missing fields, empty values, wrong types,
    duplicate tags, scale ranges, formatting and confidence. Duplicate careers
    and relationship integrity are cross-file checks done by the loader.
    """
    if not isinstance(data, dict):
        return ["profile is not a JSON object"]
    issues: list[str] = []
    for name in REQUIRED_FIELDS:
        if name not in data:
            issues.append(f"missing field: {name}")
            continue
        value = data[name]
        if name in _PAIR_FIELDS:
            if (not isinstance(value, list) or not value or not all(
                isinstance(p, list) and len(p) == 2
                and all(isinstance(x, str) and x.strip() for x in p)
                for p in value
            )):
                issues.append(f"{name} must be a non-empty list of [str, str] pairs")
        elif name in _STR_LIST_FIELDS:
            if (not isinstance(value, list) or not value
                    or not all(isinstance(x, str) and x.strip() for x in value)):
                issues.append(f"{name} must be a non-empty list of strings")
        elif name in _FLOAT_FIELDS:
            if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
                issues.append(f"{name} must be a number in [0, 1]")
        elif name in _INT_FIELDS:
            if not isinstance(value, int) or value < 0:
                issues.append(f"{name} must be a non-negative integer")
            elif name in _SCALE_FIELDS and not (1 <= value <= 5):
                issues.append(f"{name} must be within 1..5")
        else:  # plain string field
            if not isinstance(value, str) or not value.strip():
                issues.append(f"{name} must be a non-empty string")

    if not issues:
        tags = [t.lower() for t in data["tags"]]
        if len(tags) != len(set(tags)):
            issues.append("duplicate tags")
        if data["salary_entry_lpa"] > data["salary_senior_lpa"]:
            issues.append("salary_entry_lpa exceeds salary_senior_lpa")
        if data["visa_difficulty"] not in ("low", "moderate", "high"):
            issues.append("visa_difficulty must be low|moderate|high")
        if float(data["confidence"]) < 0.4:
            issues.append("confidence below acceptance threshold (0.4)")
        if data["schema_version"] != SCHEMA_VERSION:
            issues.append(f"schema_version must be {SCHEMA_VERSION}")
    return issues


def profile_from_json(data: dict) -> CareerProfile:
    """Build the typed profile from validated JSON (lists become tuples)."""
    kwargs: dict = {}
    for f in fields(CareerProfile):
        value = data[f.name]
        if f.name in _PAIR_FIELDS:
            kwargs[f.name] = tuple((p[0], p[1]) for p in value)
        elif f.name in _STR_LIST_FIELDS:
            kwargs[f.name] = tuple(value)
        elif f.name in _FLOAT_FIELDS:
            kwargs[f.name] = float(value)
        else:
            kwargs[f.name] = value
    return CareerProfile(**kwargs)


def profile_to_json(profile: CareerProfile) -> dict:
    out: dict = {}
    for f in fields(CareerProfile):
        value = getattr(profile, f.name)
        if f.name in _PAIR_FIELDS:
            out[f.name] = [list(p) for p in value]
        elif isinstance(value, tuple):
            out[f.name] = list(value)
        else:
            out[f.name] = value
    return out


def load_json_file(path: Path) -> tuple[dict | None, str]:
    """Parse one JSON file; returns (data, error). Invalid JSON never raises."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path.name}: {exc}"
