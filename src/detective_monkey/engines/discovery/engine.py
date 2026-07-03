"""The Discovery Engine — recommendations become hypotheses, actions become
evidence (v3 "Close the loop").

Designs the smallest next experiment a student can run to test a career
hypothesis, calibrated to their age/class, ability and working style
(calibration.py), built from the career's own knowledge-base material
(catalog.py). After the student reflects, the reflection becomes EXPERIENCE
evidence: the structured part deterministically, the open text through the
same validated extraction pipeline the assessment uses.

Design is deterministic (a decision); the optional LLM may only rephrase the
briefing text — never the task, difficulty, or time budget — and any invalid
output falls back to the deterministic brief.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from ..student_evidence.affinity import career_descriptor_features
from ..student_evidence.extraction import (
    PromptSection,
    extract_with_ai,
    heuristic_extraction,
)
from ..student_evidence.schema import (
    ExtractedFeature,
    OpenResponse,
    StudentEvidenceProfile,
)
from .calibration import Calibration, calibrate
from .catalog import choose_action

ENGINE_VERSION = "discovery-v1"

# Evidence lines carrying these prefixes are lived experience, not self-report.
EXPERIENCE_PREFIXES = ("Tried it:", "Experiment reflection:")

# Statuses an experiment moves through.
PROPOSED, ACCEPTED, COMPLETED, SKIPPED = "proposed", "accepted", "completed", "skipped"


@dataclass(frozen=True, slots=True)
class Reflection:
    """The 2-minute micro-pulse after an experiment. All scales are 1–5."""

    enjoyment: float
    energy: float             # drained (1) ←→ energized (5)
    would_do_again: float
    text: str = ""

    def __post_init__(self) -> None:
        for name in ("enjoyment", "energy", "would_do_again"):
            value = getattr(self, name)
            if not (1.0 <= value <= 5.0):
                raise ValueError(f"Reflection.{name} must be within [1, 5]")


@dataclass(frozen=True, slots=True)
class Experiment:
    """One testable action against one career hypothesis."""

    id: str
    student_id: str
    career_id: str
    career_name: str
    title: str
    brief: str                       # friendly one-paragraph briefing
    task: str                        # the concrete thing to do
    steps: tuple[str, ...]
    modality: str                    # build | watch | read | course | join | talk
    tier_label: str                  # gentle start | hands-on | challenge
    minutes: int
    tests_features: tuple[str, ...]  # canonical features this action tests
    calibration_reasons: tuple[str, ...]
    status: str = PROPOSED
    attempt: int = 0                 # how many actions were skipped before this
    created_at: str = ""
    completed_at: str = ""
    reflection: Reflection | None = None
    score_moves: tuple[tuple[str, float, float], ...] = field(default_factory=tuple)
    # (career_name, before, after) — recorded at completion for the diff view


class DiscoveryEngine:
    """Designs calibrated experiments and turns reflections into evidence."""

    def __init__(self, llm: object | None = None) -> None:
        self._llm = llm

    # -- experiment design (deterministic decision) --------------------------

    def design(self, profile: StudentEvidenceProfile, career,
               experiment_id: str, attempt: int = 0,
               now: datetime | None = None) -> Experiment:
        now = now or datetime.now(timezone.utc)
        tests = career_descriptor_features(career)[:4]
        cal = calibrate(profile, tests)
        action = choose_action(career, cal, attempt)
        minutes = max(15, round(cal.minutes * action.minutes_factor / 15) * 15)
        brief = self._brief(profile, career, action.task, minutes, cal)
        return Experiment(
            id=experiment_id,
            student_id=profile.student_id,
            career_id=career.id,
            career_name=career.name,
            title=action.title,
            brief=brief,
            task=action.task,
            steps=action.steps,
            modality=action.modality,
            tier_label=cal.tier_label,
            minutes=minutes,
            tests_features=tests or ("curiosity",),
            calibration_reasons=cal.reasons,
            attempt=attempt,
            created_at=now.isoformat(),
        )

    def _brief(self, profile: StudentEvidenceProfile, career, task: str,
               minutes: int, cal: Calibration) -> str:
        deterministic = (
            f"You don't have to *choose* {career.name} — just taste it. "
            f"This is a ~{minutes}-minute experiment: {task} "
            f"When you're done, tell me how it felt. Whatever you feel is "
            f"useful evidence — enjoying it and hating it both count."
        )
        polished = self._polish(profile, career, deterministic)
        return polished or deterministic

    def _polish(self, profile: StudentEvidenceProfile, career,
                deterministic: str) -> str | None:
        """Optional AI rewrite of the brief's *wording* only. Validation-gated:
        anything suspicious falls back to the deterministic text."""
        if self._llm is None or not hasattr(self._llm, "generate"):
            return None
        name = profile.profile.name or "the student"
        prompt = _BriefPrompt(
            system_prompt=(
                "You rewrite a short experiment briefing for a school student in a "
                "warm, encouraging voice. Keep every fact exactly as given: the "
                "career, the task, the time estimate. Do not add new claims, "
                "promises or advice. Reply with the rewritten paragraph only."),
            sections=(
                PromptSection("Student", f"{name}, grade {profile.profile.grade or '?'}"),
                PromptSection("Briefing to rewrite", deterministic),
            ),
            user_question="Rewrite the briefing in one friendly paragraph.",
        )
        try:
            text = (self._llm.generate(prompt) or "").strip()  # type: ignore[attr-defined]
        except Exception:
            return None
        # Gate: must stay a single short paragraph and keep the core facts.
        if not text or len(text) > 600 or "\n\n" in text:
            return None
        if career.name.lower() not in text.lower():
            return None
        return text

    # -- reflection → experience evidence -------------------------------------

    def reflection_features(self, experiment: Experiment, reflection: Reflection
                            ) -> dict[str, ExtractedFeature]:
        """Deterministic part: the felt experience updates the features this
        experiment was designed to test. A single trial is deliberately damped
        (confidence 0.75) — one great or awful day is evidence, not a verdict."""
        def unit(v: float) -> float:
            return (v - 1.0) / 4.0

        value = round(0.6 * unit(reflection.enjoyment)
                      + 0.2 * unit(reflection.energy)
                      + 0.2 * unit(reflection.would_do_again), 4)
        summary = (f"Tried it: {experiment.title} — enjoyment "
                   f"{reflection.enjoyment:.0f}/5, would repeat "
                   f"{reflection.would_do_again:.0f}/5")
        features = {
            name: ExtractedFeature(score=value, confidence=0.75, evidence=(summary,))
            for name in experiment.tests_features
        }

        # Open text goes through the same validated extraction the assessment
        # uses — AI when available, deterministic keywords otherwise. The text
        # tells us *which* features the experience touched; the sliders tell
        # us *how it felt* — so extracted scores are blended with the felt
        # value (otherwise "I loved it" plus a modest keyword score could
        # drag an established feature down).
        if reflection.text.strip():
            response = OpenResponse(
                question_id=f"reflection_{experiment.id}",
                prompt=f"How did the experiment '{experiment.title}' feel?",
                text=reflection.text.strip()[:2000],
            )
            extracted = extract_with_ai(self._llm, (response,))
            if extracted is None:
                extracted = heuristic_extraction((response,))
            for name, feat in extracted.items():
                tagged = replace(
                    feat,
                    score=round((feat.score + value) / 2, 4),
                    evidence=tuple(
                        f"Experiment reflection: {e}" if not e.startswith("Experiment reflection:") else e
                        for e in feat.evidence))
                if name in features:
                    base = features[name]
                    features[name] = ExtractedFeature(
                        score=round((base.score + tagged.score) / 2, 4),
                        confidence=round(min(1.0, max(base.confidence, tagged.confidence)), 4),
                        evidence=(base.evidence + tagged.evidence)[:4],
                    )
                else:
                    features[name] = tagged
        return features


@dataclass(frozen=True, slots=True)
class _BriefPrompt:
    """Prompt package for the brief polish — the platform-wide shape."""

    system_prompt: str
    sections: tuple[PromptSection, ...]
    user_question: str


# -- serialization (persistence boundary) ---------------------------------------


def experiment_to_json(e: Experiment) -> dict:
    return {
        "id": e.id, "student_id": e.student_id, "career_id": e.career_id,
        "career_name": e.career_name, "title": e.title, "brief": e.brief,
        "task": e.task, "steps": list(e.steps), "modality": e.modality,
        "tier_label": e.tier_label, "minutes": e.minutes,
        "tests_features": list(e.tests_features),
        "calibration_reasons": list(e.calibration_reasons),
        "status": e.status, "attempt": e.attempt,
        "created_at": e.created_at, "completed_at": e.completed_at,
        "reflection": (
            {"enjoyment": e.reflection.enjoyment, "energy": e.reflection.energy,
             "would_do_again": e.reflection.would_do_again, "text": e.reflection.text}
            if e.reflection else None),
        "score_moves": [list(m) for m in e.score_moves],
    }


def experiment_from_json(data: dict) -> Experiment:
    reflection = data.get("reflection")
    return Experiment(
        id=data["id"], student_id=data["student_id"], career_id=data["career_id"],
        career_name=data.get("career_name", ""), title=data.get("title", ""),
        brief=data.get("brief", ""), task=data.get("task", ""),
        steps=tuple(data.get("steps", [])), modality=data.get("modality", ""),
        tier_label=data.get("tier_label", ""), minutes=int(data.get("minutes", 30)),
        tests_features=tuple(data.get("tests_features", [])),
        calibration_reasons=tuple(data.get("calibration_reasons", [])),
        status=data.get("status", PROPOSED), attempt=int(data.get("attempt", 0)),
        created_at=data.get("created_at", ""), completed_at=data.get("completed_at", ""),
        reflection=(Reflection(
            enjoyment=float(reflection["enjoyment"]), energy=float(reflection["energy"]),
            would_do_again=float(reflection["would_do_again"]),
            text=reflection.get("text", "")) if reflection else None),
        score_moves=tuple(
            (m[0], float(m[1]), float(m[2])) for m in data.get("score_moves", [])),
    )


# -- evidence strength ---------------------------------------------------------


def evidence_strength(profile: StudentEvidenceProfile, career) -> int:
    """How much of this hypothesis rests on lived experience (0–100).
    Share of the career's descriptor features whose evidence contains at
    least one experiment-backed line."""
    descriptors = career_descriptor_features(career)[:6]
    if not descriptors:
        return 0
    tested = 0
    for name in descriptors:
        feat = profile.feature(name)
        if feat is not None and any(
                e.startswith(EXPERIENCE_PREFIXES) for e in feat.evidence):
            tested += 1
    return round(tested / len(descriptors) * 100)
