"""Student calibration — deterministic, explainable task fitting.

Decides *how* an experiment should be shaped for one particular student:
effort band (age/class), challenge tier (academic record + relevant feature
scores), and preferred modalities (how they like to learn and work). Every
output carries a human-readable reason, because a student — and a parent —
must always be able to ask "why was I given this task?".

This is a decision, so it sits on the deterministic side of the intelligence
boundary (18 §16): no AI is consulted. The AI may later rephrase the wording
of a brief; it never chooses the task, the difficulty or the time budget.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..student_evidence.schema import StudentEvidenceProfile

# Action modalities, matched to knowledge-base material in catalog.py.
WATCH = "watch"        # videos / documentaries + journal
READ = "read"          # books / articles + summarize
BUILD = "build"        # portfolio projects, making things
COURSE = "course"      # short structured course
JOIN = "join"          # communities, clubs, group activity
TALK = "talk"          # interview a professional / teacher

ALL_MODALITIES = (BUILD, WATCH, TALK, READ, COURSE, JOIN)

# Effort bands by school stage. Minutes are per experiment, not per sitting.
_EFFORT_BANDS = (
    # (max_grade, band_name, minutes by tier (gentle, core, stretch))
    (8, "explorer", (30, 45, 60)),
    (10, "builder", (45, 90, 120)),
    (99, "specialist", (60, 120, 240)),
)

_TIER_LABELS = {1: "gentle start", 2: "hands-on", 3: "challenge"}


@dataclass(frozen=True, slots=True)
class Calibration:
    """How experiments should be shaped for this student right now."""

    stage: str                       # explorer | builder | specialist
    grade: int | None
    tier: int                        # 1 gentle · 2 core · 3 stretch
    tier_label: str
    minutes: int                     # time budget for one experiment
    modalities: tuple[str, ...]      # preference-ordered
    solo: bool                       # prefers working alone vs with others
    reasons: tuple[str, ...]         # why these choices — always shown


def _parse_grade(profile: StudentEvidenceProfile) -> int | None:
    raw = (profile.profile.grade or "").strip().lower()
    digits = "".join(c for c in raw if c.isdigit())
    if digits:
        try:
            grade = int(digits)
            if 1 <= grade <= 12:
                return grade
        except ValueError:
            pass
    # Fall back to age: Indian school grades run roughly age = grade + 5.
    if profile.profile.age:
        grade = profile.profile.age - 5
        if 1 <= grade <= 12:
            return grade
    return None


def _feature_score(profile: StudentEvidenceProfile, name: str,
                   default: float = 0.5) -> float:
    feat = profile.feature(name)
    return feat.score if feat is not None else default


def _ability(profile: StudentEvidenceProfile,
             relevant_features: tuple[str, ...]) -> tuple[float, str]:
    """Blend academic evidence with the features the experiment will test.
    Missing sources simply drop out — never penalize absent data."""
    parts: list[tuple[float, str]] = []
    if profile.academic:
        academic = sum(a.average_score for a in profile.academic) / len(profile.academic) / 100.0
        parts.append((academic, f"school average {academic * 100:.0f}%"))
    feats = [profile.feature(f) for f in relevant_features]
    feats = [f for f in feats if f is not None]
    if feats:
        strength = sum(f.score for f in feats) / len(feats)
        parts.append((strength, "strength in the skills this career uses"))
    if not parts:
        return 0.5, "no ability evidence yet — starting in the middle"
    value = sum(v for v, _ in parts) / len(parts)
    return value, " and ".join(r for _, r in parts)


def _modalities(profile: StudentEvidenceProfile) -> tuple[tuple[str, ...], str]:
    """Order task modalities by the student's own evidence."""
    scores = {
        BUILD: _feature_score(profile, "hands_on_work") * 0.6
               + _feature_score(profile, "technical_interest") * 0.2
               + _feature_score(profile, "learning_style") * 0.2,
        WATCH: _feature_score(profile, "curiosity") * 0.6
               + (1.0 - _feature_score(profile, "hands_on_work")) * 0.4,
        READ: _feature_score(profile, "research_interest") * 0.6
              + _feature_score(profile, "attention_to_detail") * 0.4,
        COURSE: _feature_score(profile, "analytical_thinking") * 0.5
                + _feature_score(profile, "attention_to_detail") * 0.5,
        JOIN: _feature_score(profile, "teamwork") * 0.6
              + _feature_score(profile, "people_interaction") * 0.4,
        TALK: _feature_score(profile, "people_interaction") * 0.5
              + _feature_score(profile, "communication") * 0.5,
    }
    ordered = tuple(sorted(ALL_MODALITIES, key=lambda m: -scores[m]))
    leaders = {BUILD: "you learn best by making things",
               WATCH: "you love absorbing how things work",
               READ: "you enjoy going deep through reading",
               COURSE: "structured learning suits you",
               JOIN: "you thrive around other people",
               TALK: "you learn well through conversations"}
    return ordered, leaders[ordered[0]]


def calibrate(profile: StudentEvidenceProfile,
              relevant_features: tuple[str, ...] = ()) -> Calibration:
    """Fit experiment parameters to this student — age/class, ability,
    working style — with reasons for every choice."""
    grade = _parse_grade(profile)
    effective = grade if grade is not None else 9  # neutral default: mid-school
    for max_grade, stage, minute_bands in _EFFORT_BANDS:
        if effective <= max_grade:
            break

    ability, ability_reason = _ability(profile, relevant_features)
    tier = 1 if ability < 0.45 else (3 if ability >= 0.75 else 2)

    modalities, modality_reason = _modalities(profile)
    solo = _feature_score(profile, "independence") >= _feature_score(profile, "teamwork")

    reasons = (
        (f"Sized for grade {grade}" if grade is not None
         else "Sized for a mid-school student (grade unknown)"),
        f"{_TIER_LABELS[tier].capitalize()} difficulty — {ability_reason}",
        f"Format picked because {modality_reason}",
    )
    return Calibration(
        stage=stage,
        grade=grade,
        tier=tier,
        tier_label=_TIER_LABELS[tier],
        minutes=minute_bands[tier - 1],
        modalities=modalities,
        solo=solo,
        reasons=reasons,
    )
