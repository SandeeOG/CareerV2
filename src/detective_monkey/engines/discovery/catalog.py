"""Action catalog — experiment raw material from the Career Knowledge Base.

Careers already carry portfolio ideas, projects, videos, books, courses and
communities (knowledge/careers/schema.py). This module turns those fields
into concrete, testable actions per modality. Deterministic: the same student
+ career + attempt always yields the same action, and skipping rotates to the
next material rather than repeating.
"""

from __future__ import annotations

from dataclasses import dataclass

from .calibration import BUILD, COURSE, JOIN, READ, TALK, WATCH, Calibration


@dataclass(frozen=True, slots=True)
class ActionTemplate:
    modality: str
    title: str
    task: str                    # the concrete thing to do
    steps: tuple[str, ...]
    minutes_factor: float        # scales the calibration time budget


def _first(items, index: int) -> str | None:
    items = [i for i in items if i and str(i).strip()]
    if not items:
        return None
    return str(items[index % len(items)]).strip()


def _templates_for(career, calibration: Calibration, attempt: int
                   ) -> dict[str, ActionTemplate]:
    """One candidate action per modality, built from the career's own data.
    ``attempt`` rotates through the material so a skipped experiment is
    replaced by a different task, not the same one again. A stable per-career
    offset varies material between careers that share resource lists."""
    name = career.name
    attempt = attempt + sum(ord(c) for c in career.id) % 3
    out: dict[str, ActionTemplate] = {}

    project = _first(tuple(career.portfolio_ideas) + tuple(career.projects), attempt)
    if project:
        # Gentle tier turns a build into a plan-and-start, not a finish.
        scope = ("Plan it and build just the first small piece"
                 if calibration.tier == 1 else "Build a small working version")
        out[BUILD] = ActionTemplate(
            BUILD, f"Try the work: {project}",
            f"{scope} of: {project}.",
            (f"Set a timer — this is a taste of {name}, not a masterpiece.",
             f"{scope.rstrip('.')}.",
             "Note the moment you felt most absorbed — and the moment you wanted to quit.",
             "Keep whatever you made; unfinished counts."),
            1.0)

    video = _first(career.youtube, attempt)
    if video:
        out[WATCH] = ActionTemplate(
            WATCH, f"Watch the real thing: {video}",
            f"Watch {video} (or any 'day in the life of a {name.lower()} professional' video).",
            ("Watch actively — pause when something surprises you.",
             "Write down 3 things that excited you and 1 thing that put you off.",
             "Ask yourself: could I do the boring parts of this every day?"),
            0.6)

    book = _first(career.books, attempt)
    if book:
        out[READ] = ActionTemplate(
            READ, f"Read into it: {book}",
            f"Read the first chapter (or a detailed summary) of {book}.",
            ("Read the first chapter or a quality summary/review.",
             "Note 2 ideas you'd want to explore further.",
             "Would you willingly read the rest? That answer is evidence."),
            0.7)

    course = _first(career.courses, attempt)
    if course:
        out[COURSE] = ActionTemplate(
            COURSE, f"Sample a course: {course}",
            f"Do only the first lesson/module of {course} (free preview is fine).",
            ("Complete just the first lesson — no commitment beyond that.",
             "Notice whether you want lesson two. Wanting more is the signal.",
             "Write one sentence about what surprised you."),
            0.9)

    community = _first(career.communities, attempt)
    if community:
        out[JOIN] = ActionTemplate(
            JOIN, f"Lurk with professionals: {community}",
            f"Spend time reading real discussions in {community}.",
            ("Read the top posts of this week — what do these people worry about?",
             "Find one problem they discuss that you'd enjoy solving.",
             "Optional: ask one genuine question."),
            0.5)

    # TALK is always available — every career has humans.
    employer = _first(getattr(career, "typical_employers", ()), attempt)
    who = f"someone working in {name.lower()}"
    if employer:
        who += f" (e.g. at {employer})"
    out[TALK] = ActionTemplate(
        TALK, f"Talk to a real {name.lower()} professional",
        f"Have a 15-minute conversation with {who} — or a teacher/relative who knows the field.",
        ("Prepare 3 questions: What does a normal Tuesday look like? "
         "What's the worst part? What would you tell your 15-year-old self?",
         "Have the conversation — in person, call, or even chat.",
         "Write down the answer that surprised you most."),
        0.5)

    return out


def choose_action(career, calibration: Calibration, attempt: int = 0
                  ) -> ActionTemplate:
    """Pick the best-fitting action: the student's most-preferred modality
    that the career has material for; rotate on retries/skips."""
    templates = _templates_for(career, calibration, attempt)
    ordered = [m for m in calibration.modalities if m in templates]
    if not ordered:  # TALK guarantees this never triggers, but stay safe
        ordered = list(templates)
    # Rotation on skip: move to the next preferred modality.
    modality = ordered[attempt % len(ordered)]
    return templates[modality]
