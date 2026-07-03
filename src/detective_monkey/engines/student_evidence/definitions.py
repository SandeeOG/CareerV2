"""Career Compass v2 — the expanded evidence assessment, as data.

Question text and feature mappings are versioned data, never engine logic. The
assessment is conversational: 6 sections (Interests, Personality, Work
Preferences, Career Values, Strengths, Career Aspirations) mixing structured
questions (Likert, single/multi choice, scenarios) with short open-ended
questions. Structured questions provide reliable scoring; open questions give
the AI extractor richer context.

Also defines the Career Pulse — a lightweight 10-question follow-up presented
every six months.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ASSESSMENT_ID = "career-compass-v2"
ASSESSMENT_VERSION = 2

# Career Pulse cadence (six months).
PULSE_INTERVAL_DAYS = 182

# Question kinds.
LIKERT = "likert"                # 1-5 agreement scale
SINGLE_CHOICE = "single_choice"  # pick one option
MULTI_CHOICE = "multi_choice"    # pick up to `max_choices`
SCENARIO = "scenario"            # single choice framed as a situation
OPEN = "open"                    # one-paragraph free text


@dataclass(frozen=True, slots=True)
class Option:
    """A selectable option. `features` maps the choice onto canonical features
    as (feature_name, value) pairs, value in [0, 1]."""

    id: str
    label: str
    features: tuple[tuple[str, float], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvidenceQuestion:
    """One question. For Likert questions `features` weights the (normalized,
    possibly reversed) agreement onto canonical features."""

    id: str
    section: str
    kind: str
    prompt: str
    features: tuple[tuple[str, float], ...] = field(default_factory=tuple)  # likert only
    options: tuple[Option, ...] = field(default_factory=tuple)
    reverse: bool = False
    max_choices: int = 3   # multi_choice only


@dataclass(frozen=True, slots=True)
class EvidenceSection:
    id: str
    title: str
    intro: str
    questions: tuple[EvidenceQuestion, ...]


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    id: str
    version: int
    sections: tuple[EvidenceSection, ...]

    def questions(self) -> tuple[EvidenceQuestion, ...]:
        return tuple(q for s in self.sections for q in s.questions)

    def structured_questions(self) -> tuple[EvidenceQuestion, ...]:
        return tuple(q for q in self.questions() if q.kind != OPEN)

    def open_questions(self) -> tuple[EvidenceQuestion, ...]:
        return tuple(q for q in self.questions() if q.kind == OPEN)

    def question(self, qid: str) -> EvidenceQuestion | None:
        for q in self.questions():
            if q.id == qid:
                return q
        return None


def _likert(qid: str, section: str, prompt: str, *features: tuple[str, float],
            reverse: bool = False) -> EvidenceQuestion:
    return EvidenceQuestion(qid, section, LIKERT, prompt,
                            features=tuple(features), reverse=reverse)


def _open(qid: str, section: str, prompt: str) -> EvidenceQuestion:
    return EvidenceQuestion(qid, section, OPEN, prompt)


# ---------------------------------------------------------------------------
# Section 1 — Interests
# ---------------------------------------------------------------------------

_INTERESTS = EvidenceSection(
    "interests", "Your Interests",
    "Let's find out what genuinely pulls your attention — there are no right answers.",
    (
        EvidenceQuestion(
            "int_free_time", "interests", SINGLE_CHOICE,
            "It's a free Sunday afternoon. Which of these sounds most like you?",
            options=(
                Option("build", "Building or fixing something (an app, a gadget, a model)",
                       (("technical_interest", 0.9), ("hands_on_work", 0.8))),
                Option("create", "Drawing, writing, making music or videos",
                       (("artistic_interest", 0.9), ("creativity", 0.8))),
                Option("organize", "Organizing an event or running a small venture",
                       (("business_interest", 0.85), ("leadership", 0.7), ("entrepreneurship", 0.7))),
                Option("learn", "Reading or watching videos about how the world works",
                       (("curiosity", 0.9), ("research_interest", 0.8))),
                Option("help", "Volunteering, coaching or helping someone out",
                       (("helping_others", 0.9), ("people_interaction", 0.8))),
            )),
        EvidenceQuestion(
            "int_school_subjects", "interests", MULTI_CHOICE,
            "Which school subjects do you actually look forward to? (pick up to 3)",
            max_choices=3,
            options=(
                Option("maths", "Mathematics", (("analytical_thinking", 0.85), ("problem_solving", 0.7))),
                Option("science", "Science (Physics / Chemistry / Biology)",
                       (("research_interest", 0.8), ("curiosity", 0.7))),
                Option("cs", "Computer Science / IT", (("technical_interest", 0.9),)),
                Option("arts", "Art / Music / Design", (("artistic_interest", 0.9), ("creativity", 0.7))),
                Option("lang", "Languages / Literature", (("communication", 0.8),)),
                Option("social", "History / Civics / Geography", (("curiosity", 0.6), ("research_interest", 0.5))),
                Option("commerce", "Business Studies / Economics", (("business_interest", 0.9),)),
                Option("sports", "Physical Education / Sports", (("hands_on_work", 0.7), ("teamwork", 0.6))),
            )),
        _likert("int_tech", "interests",
                "I enjoy figuring out how machines, apps or systems work.",
                ("technical_interest", 1.0), ("curiosity", 0.4)),
        _likert("int_art", "interests",
                "I often get lost in creative activities like designing, writing or making things look good.",
                ("artistic_interest", 1.0), ("creativity", 0.5)),
        _likert("int_business", "interests",
                "The idea of running my own business or making deals excites me.",
                ("business_interest", 0.9), ("entrepreneurship", 0.8)),
        _likert("int_science", "interests",
                "I like digging into a topic deeply until I truly understand it.",
                ("research_interest", 0.9), ("curiosity", 0.6)),
        _likert("int_people", "interests",
                "Days spent mostly working with people energize me more than days spent working alone.",
                ("people_interaction", 0.9), ("helping_others", 0.4)),
        _open("int_open_subject", "interests",
              "What school subject do you enjoy the most, and what makes it enjoyable for you?"),
        _open("int_open_learned", "interests",
              "Describe something you learned recently — inside or outside school — that genuinely excited you."),
    ),
)

# ---------------------------------------------------------------------------
# Section 2 — Personality
# ---------------------------------------------------------------------------

_PERSONALITY = EvidenceSection(
    "personality", "How You Think",
    "A few questions about your natural style — how you approach problems and people.",
    (
        _likert("per_analagain", "personality",
                "Before deciding anything important, I like to break the problem into smaller pieces.",
                ("analytical_thinking", 1.0)),
        _likert("per_instinct", "personality",
                "I usually go with my gut instead of analyzing things.",
                ("analytical_thinking", 0.8), reverse=True),
        _likert("per_ideas", "personality",
                "People say I come up with unusual ideas or unexpected solutions.",
                ("creativity", 1.0)),
        _likert("per_lead", "personality",
                "In group projects, I naturally end up coordinating who does what.",
                ("leadership", 1.0)),
        _likert("per_explain", "personality",
                "I can explain a complicated idea so that a younger student would get it.",
                ("communication", 1.0)),
        _likert("per_detail", "personality",
                "I notice small mistakes — a wrong number, a misaligned design — that others miss.",
                ("attention_to_detail", 1.0)),
        _likert("per_risk", "personality",
                "I'd rather try something with an uncertain outcome than stick to the safe option.",
                ("risk_tolerance", 1.0), ("entrepreneurship", 0.3)),
        EvidenceQuestion(
            "per_stuck", "personality", SCENARIO,
            "You're stuck on a hard problem for an hour. What do you actually do?",
            options=(
                Option("dissect", "Slow down and dissect it step by step until it cracks",
                       (("analytical_thinking", 0.9), ("problem_solving", 0.85))),
                Option("experiment", "Try wild alternatives until something works",
                       (("creativity", 0.8), ("risk_tolerance", 0.6), ("problem_solving", 0.6))),
                Option("ask", "Ask a friend or teacher to think it through with me",
                       (("teamwork", 0.85), ("people_interaction", 0.6))),
                Option("research", "Search for how others solved similar problems",
                       (("research_interest", 0.8), ("curiosity", 0.6))),
            )),
        _open("per_open_proud", "personality",
              "What achievement are you most proud of so far? What did it take from you?"),
    ),
)

# ---------------------------------------------------------------------------
# Section 3 — Work Preferences
# ---------------------------------------------------------------------------

_WORK = EvidenceSection(
    "work_preferences", "How You Like to Work",
    "Everyone works differently. Help us understand your ideal working day.",
    (
        EvidenceQuestion(
            "wrk_setting", "work_preferences", SINGLE_CHOICE,
            "Pick the working day that sounds best:",
            options=(
                Option("team", "Brainstorming and building things with a close team",
                       (("teamwork", 0.9), ("people_interaction", 0.7))),
                Option("solo", "Deep, focused work on my own project, headphones on",
                       (("independence", 0.9),)),
                Option("field", "Out in the field — moving, making, measuring, meeting",
                       (("hands_on_work", 0.9), ("people_interaction", 0.5))),
                Option("mix", "A mix — some collaboration, some quiet focus time",
                       (("teamwork", 0.6), ("independence", 0.6))),
            )),
        _likert("wrk_hands", "work_preferences",
                "I'd rather make something with my hands than write a report about it.",
                ("hands_on_work", 1.0)),
        _likert("wrk_alone", "work_preferences",
                "I do my best work when I'm left alone to figure things out.",
                ("independence", 1.0)),
        _likert("wrk_team", "work_preferences",
                "Working in a team usually produces better results than working alone.",
                ("teamwork", 0.9)),
        EvidenceQuestion(
            "wrk_style", "work_preferences", SINGLE_CHOICE,
            "How do you learn a new skill fastest?",
            options=(
                Option("doing", "By doing — jump in, break things, fix them",
                       (("learning_style", 0.9), ("hands_on_work", 0.5))),
                Option("theory", "By understanding the theory first, then practising",
                       (("learning_style", 0.7), ("analytical_thinking", 0.4))),
                Option("watching", "By watching someone skilled, then imitating",
                       (("learning_style", 0.5),)),
                Option("group", "By studying with friends and testing each other",
                       (("learning_style", 0.6), ("teamwork", 0.4))),
            )),
        _likert("wrk_structure", "work_preferences",
                "I prefer clear instructions over open-ended tasks.",
                ("independence", 0.7), reverse=True),
    ),
)

# ---------------------------------------------------------------------------
# Section 4 — Career Values
# ---------------------------------------------------------------------------

_VALUES = EvidenceSection(
    "career_values", "What Matters to You",
    "When you imagine a good career, what actually matters?",
    (
        EvidenceQuestion(
            "val_priority", "career_values", MULTI_CHOICE,
            "Which of these matter most in your future career? (pick up to 3)",
            max_choices=3,
            options=(
                Option("impact", "Making a difference in people's lives",
                       (("helping_others", 0.85),)),
                Option("money", "Earning very well", (("business_interest", 0.5),)),
                Option("freedom", "Being my own boss",
                       (("entrepreneurship", 0.85), ("independence", 0.6))),
                Option("mastery", "Becoming a true expert at something hard",
                       (("research_interest", 0.6), ("attention_to_detail", 0.5))),
                Option("stability", "Security and a stable, respected job",
                       (("risk_tolerance", 0.15),)),
                Option("fame", "Recognition for creative work",
                       (("artistic_interest", 0.6), ("creativity", 0.4))),
                Option("adventure", "Travel, variety and new experiences",
                       (("international_interest", 0.7), ("risk_tolerance", 0.5))),
            )),
        _likert("val_help", "career_values",
                "A career that helps others would feel more meaningful to me than one that just pays well.",
                ("helping_others", 0.9)),
        _likert("val_global", "career_values",
                "I'd love to study or work in another country someday.",
                ("international_interest", 1.0)),
        _likert("val_relocate", "career_values",
                "I'd happily move to a new city if a great opportunity required it.",
                ("relocation_preference", 1.0)),
        _likert("val_startup", "career_values",
                "I'd rather build something of my own than climb the ladder in a big company.",
                ("entrepreneurship", 0.9), ("risk_tolerance", 0.4)),
        _open("val_open_impact", "career_values",
              "What kind of impact would you like your future career to have on the world around you?"),
        _open("val_open_problem", "career_values",
              "If you could solve one real-world problem, what would it be — and why that one?"),
    ),
)

# ---------------------------------------------------------------------------
# Section 5 — Strengths
# ---------------------------------------------------------------------------

_STRENGTHS = EvidenceSection(
    "strengths", "Your Strengths",
    "Time to be honest about what you're good at (and what you're still building).",
    (
        _likert("str_solve", "strengths",
                "Friends come to me when they have a tricky problem to untangle.",
                ("problem_solving", 1.0), ("analytical_thinking", 0.4)),
        _likert("str_speak", "strengths",
                "I'm comfortable presenting or speaking in front of the class.",
                ("communication", 0.9), ("people_interaction", 0.4)),
        _likert("str_finish", "strengths",
                "When I start something, I see it through — even when it gets boring.",
                ("attention_to_detail", 0.7)),
        _likert("str_curious", "strengths",
                "I ask 'why' and 'what if' more than most people around me.",
                ("curiosity", 1.0)),
        EvidenceQuestion(
            "str_role", "strengths", SCENARIO,
            "Your class is putting on a big event. Which role would you claim?",
            options=(
                Option("lead", "Overall coordinator — own the plan, rally the team",
                       (("leadership", 0.9), ("communication", 0.5))),
                Option("design", "Creative director — posters, stage, the vibe",
                       (("artistic_interest", 0.85), ("creativity", 0.7))),
                Option("budget", "Budget and logistics — money, timing, checklists",
                       (("attention_to_detail", 0.85), ("analytical_thinking", 0.5), ("business_interest", 0.4))),
                Option("tech", "Tech crew — sound, lights, livestream",
                       (("technical_interest", 0.85), ("hands_on_work", 0.6))),
                Option("host", "Host / anchor — on stage, working the crowd",
                       (("communication", 0.9), ("people_interaction", 0.7))),
            )),
        _open("str_open_strength", "strengths",
              "What's one thing you're genuinely good at that school grades don't capture?"),
        _open("str_open_hard", "strengths",
              "Tell us about a time something was really hard. How did you deal with it?"),
    ),
)

# ---------------------------------------------------------------------------
# Section 6 — Career Aspirations
# ---------------------------------------------------------------------------

_ASPIRATIONS = EvidenceSection(
    "aspirations", "Your Aspirations",
    "Finally — where do you imagine yourself heading? Rough answers are fine.",
    (
        _likert("asp_confident", "aspirations",
                "I have a fairly clear idea of what career I want.",
                ("career_confidence", 1.0)),
        _likert("asp_explore", "aspirations",
                "I'm open to discovering careers I've never heard of.",
                ("curiosity", 0.5)),
        EvidenceQuestion(
            "asp_tenyears", "aspirations", SINGLE_CHOICE,
            "Ten years from now, which headline about you would feel best?",
            options=(
                Option("founder", "\"…launches startup that changes the industry\"",
                       (("entrepreneurship", 0.9), ("risk_tolerance", 0.6))),
                Option("expert", "\"…publishes breakthrough research\"",
                       (("research_interest", 0.9), ("analytical_thinking", 0.5))),
                Option("creator", "\"…work exhibited / streamed by millions\"",
                       (("artistic_interest", 0.9), ("creativity", 0.6))),
                Option("leader", "\"…youngest to lead a major organization\"",
                       (("leadership", 0.9), ("business_interest", 0.6))),
                Option("changemaker", "\"…initiative transforms thousands of lives\"",
                       (("helping_others", 0.9), ("leadership", 0.4))),
                Option("builder", "\"…engineers the system everyone now relies on\"",
                       (("technical_interest", 0.9), ("problem_solving", 0.5))),
            )),
        _open("asp_open_future", "aspirations",
              "What kind of work do you imagine yourself enjoying ten years from now? Describe a day of it."),
        _open("asp_open_dream", "aspirations",
              "Is there a dream career (or two) already on your mind? What draws you to it?"),
        _open("asp_open_worry", "aspirations",
              "What worries you most when you think about choosing a career?"),
    ),
)


EVIDENCE_ASSESSMENT = EvidenceAssessment(
    id=ASSESSMENT_ID,
    version=ASSESSMENT_VERSION,
    sections=(_INTERESTS, _PERSONALITY, _WORK, _VALUES, _STRENGTHS, _ASPIRATIONS),
)


# ---------------------------------------------------------------------------
# Career Pulse — max 10 questions, every six months. Updates interests and
# goals without repeating the whole assessment.
# ---------------------------------------------------------------------------

CAREER_PULSE = EvidenceAssessment(
    id="career-pulse-v1",
    version=1,
    sections=(
        EvidenceSection(
            "pulse", "Career Pulse",
            "A five-minute check-in. What's changed since last time?",
            (
                _likert("pls_tech", "pulse",
                        "These days, technology and how things work interests me.",
                        ("technical_interest", 1.0)),
                _likert("pls_art", "pulse",
                        "These days, creative work pulls me in.",
                        ("artistic_interest", 1.0), ("creativity", 0.4)),
                _likert("pls_business", "pulse",
                        "These days, business and entrepreneurship excite me.",
                        ("business_interest", 0.9), ("entrepreneurship", 0.6)),
                _likert("pls_research", "pulse",
                        "These days, I enjoy going deep into topics and research.",
                        ("research_interest", 1.0), ("curiosity", 0.4)),
                _likert("pls_people", "pulse",
                        "These days, I prefer work that involves lots of people.",
                        ("people_interaction", 1.0)),
                _likert("pls_confident", "pulse",
                        "I'm clearer about my career direction than I was six months ago.",
                        ("career_confidence", 1.0)),
                _likert("pls_global", "pulse",
                        "Studying or working abroad appeals to me right now.",
                        ("international_interest", 1.0)),
                EvidenceQuestion(
                    "pls_focus", "pulse", SINGLE_CHOICE,
                    "What do you most want help with right now?",
                    options=(
                        Option("discover", "Discovering more career options",
                               (("curiosity", 0.6),)),
                        Option("decide", "Deciding between careers I already like",
                               (("career_confidence", 0.6),)),
                        Option("plan", "Planning the path to a career I've chosen",
                               (("career_confidence", 0.85),)),
                        Option("skills", "Building skills for my chosen direction",
                               (("career_confidence", 0.8), ("hands_on_work", 0.4))),
                    )),
                _open("pls_open_new", "pulse",
                      "Anything new you've tried or discovered recently that changed how you think about careers?"),
                _open("pls_open_goal", "pulse",
                      "Has your dream career changed? What is it now?"),
            ),
        ),
    ),
)


# -- serialization -----------------------------------------------------------


def assessment_to_json(a: EvidenceAssessment) -> dict:
    return {
        "id": a.id,
        "version": a.version,
        "structured_count": len(a.structured_questions()),
        "open_count": len(a.open_questions()),
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "intro": s.intro,
                "questions": [
                    {
                        "id": q.id,
                        "kind": q.kind,
                        "prompt": q.prompt,
                        "max_choices": q.max_choices if q.kind == MULTI_CHOICE else None,
                        "options": [{"id": o.id, "label": o.label} for o in q.options],
                    }
                    for q in s.questions
                ],
            }
            for s in a.sections
        ],
    }
