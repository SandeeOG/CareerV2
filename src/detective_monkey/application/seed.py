"""Seeded demo dataset + backend composition.

Provides a coherent, self-contained configuration (assessment, features,
reasoning, careers, knowledge) so the platform runs a complete student journey
out of the box. This is *configuration data*, not business logic — the engines
and services are unchanged. A real deployment would load equivalent data from
the configuration service / repositories.
"""

from __future__ import annotations

from .container import Backend
from ..domain.career.career import Career
from ..domain.career.identity import CareerIdentity
from ..domain.career.layers import KnowledgeAreaRequirement, PersonalityRequirement
from ..domain.common.identifiers import CareerId, SkillId
from ..domain.common.scores import Importance, ProficiencyLevel, Score, ScoreRange
from ..domain.common.versioning import Version
from ..domain.recommendation.dimensions import Dimension
from ..domain.recommendation.weights import WeightConfiguration
from ..domain.skills.career_skill import CareerSkill
from ..engines.assessment.definitions import (
    AssessmentDefinition,
    Question,
    Section,
)
from ..engines.feature_engineering.definitions import (
    FeatureCategory,
    FeatureDefinition,
    FeatureType,
)
from ..engines.student_intelligence.config import (
    AggregationRule,
    ConstructSource,
    DerivedFeatureSpec,
    ReasoningConfig,
)
from ..domain.common.scores import UnitInterval

ASSESSMENT_ID = "career-compass-v1"
_V1 = Version(1)

# Constructs the demo assessment measures.
CONSTRUCTS = (
    "analytical_thinking",
    "creativity",
    "leadership",
    "communication",
    "curiosity",
    "conscientiousness",
)

# (construct, prompt, reverse_scored)
_QUESTIONS = [
    ("analytical_thinking", "I enjoy breaking complex problems into smaller parts.", False),
    ("analytical_thinking", "I prefer to act on instinct rather than analysis.", True),
    ("creativity", "I often come up with original ideas or approaches.", False),
    ("creativity", "I find it hard to imagine new possibilities.", True),
    ("leadership", "I naturally take charge when working in a group.", False),
    ("leadership", "I prefer others to make the important decisions.", True),
    ("communication", "I can explain difficult ideas clearly to others.", False),
    ("communication", "I struggle to express my thoughts in words.", True),
    ("curiosity", "I love learning about how and why things work.", False),
    ("curiosity", "I rarely seek out new topics on my own.", True),
    ("conscientiousness", "I plan my work carefully and follow through.", False),
    ("conscientiousness", "I often leave tasks unfinished.", True),
]


def default_assessment_definition() -> AssessmentDefinition:
    questions = tuple(
        Question(
            id=f"q{i + 1}",
            construct=construct,
            reverse_scored=reverse,
            scale_min=1,
            scale_max=5,
            prompt=prompt,
        )
        for i, (construct, prompt, reverse) in enumerate(_QUESTIONS)
    )
    return AssessmentDefinition(
        id=ASSESSMENT_ID,
        version=_V1,
        sections=(Section("core", "Career Compass", questions),),
    )


def default_feature_definitions() -> tuple[FeatureDefinition, ...]:
    return tuple(
        FeatureDefinition(
            id=f"f_{c}",
            name=c.replace("_", " ").title(),
            category=FeatureCategory.PSYCHOMETRIC,
            output_type=FeatureType.PERCENTAGE,
            formula_id="evidence_mean",
            version=_V1,
            inputs=(c,),
        )
        for c in CONSTRUCTS
    )


def default_reasoning_config() -> ReasoningConfig:
    return ReasoningConfig(
        version=_V1,
        construct_sources=tuple(ConstructSource(c, f"f_{c}") for c in CONSTRUCTS),
        domain_rules=(
            AggregationRule("analytical_ability",
                            (("analytical_thinking", 0.6), ("conscientiousness", 0.4))),
            AggregationRule("creative_ability",
                            (("creativity", 0.6), ("curiosity", 0.4))),
            AggregationRule("social_intelligence",
                            (("communication", 0.5), ("leadership", 0.5))),
        ),
        derived_features=(
            DerivedFeatureSpec("analytical_strength", "f_analytical_thinking"),
            DerivedFeatureSpec("creative_strength", "f_creativity"),
        ),
    )


def default_weights() -> WeightConfiguration:
    return WeightConfiguration(_V1, weights=(
        (Dimension.PSYCHOLOGICAL, UnitInterval(0.6)),
        (Dimension.KNOWLEDGE, UnitInterval(0.25)),
        (Dimension.SKILL, UnitInterval(0.15)),
    ))


# ---------------------------------------------------------------------------
# Engine-test fixtures ONLY (38/39: the application itself never uses these).
# The live application's careers, insights and knowledge nodes all come from
# the generated Career Knowledge Base via `build_demo_backend` below. These
# five tiny careers remain solely as deterministic fixtures for the engine
# unit tests (tests/test_intelligence.py, tests/test_mentor.py).
# ---------------------------------------------------------------------------


def _career(cid: str, name: str, slug: str, personality, knowledge=(), skills=()) -> Career:
    return Career(
        identity=CareerIdentity(CareerId(cid), name, slug),
        version=_V1,
        personality=personality,
        knowledge_areas=knowledge,
        skills=skills,
    )


def _p(construct: str, low: int, high: int, importance: Importance) -> PersonalityRequirement:
    return PersonalityRequirement(construct, ScoreRange(Score(low), Score(high)), importance)


def demo_careers() -> tuple[Career, ...]:
    py = SkillId("skill_python")
    return (
        _career("c_ds", "Data Scientist", "data-scientist",
                personality=(_p("analytical_thinking", 70, 100, Importance.CRITICAL),
                             _p("curiosity", 60, 100, Importance.HIGH)),
                knowledge=(KnowledgeAreaRequirement("analytical_ability", Importance.HIGH),),
                skills=(CareerSkill(CareerId("c_ds"), py, Importance.CRITICAL,
                                    ProficiencyLevel.INTERMEDIATE, ProficiencyLevel.ADVANCED),)),
        _career("c_swe", "Software Engineer", "software-engineer",
                personality=(_p("analytical_thinking", 65, 100, Importance.CRITICAL),
                             _p("conscientiousness", 55, 100, Importance.MEDIUM)),
                knowledge=(KnowledgeAreaRequirement("analytical_ability", Importance.MEDIUM),),
                skills=(CareerSkill(CareerId("c_swe"), py, Importance.HIGH,
                                    ProficiencyLevel.INTERMEDIATE, ProficiencyLevel.ADVANCED),)),
        _career("c_ux", "UX Designer", "ux-designer",
                personality=(_p("creativity", 70, 100, Importance.CRITICAL),
                             _p("communication", 60, 100, Importance.HIGH)),
                knowledge=(KnowledgeAreaRequirement("creative_ability", Importance.HIGH),)),
        _career("c_pm", "Product Manager", "product-manager",
                personality=(_p("communication", 65, 100, Importance.CRITICAL),
                             _p("leadership", 60, 100, Importance.HIGH)),
                knowledge=(KnowledgeAreaRequirement("social_intelligence", Importance.HIGH),)),
        _career("c_rs", "Research Scientist", "research-scientist",
                personality=(_p("curiosity", 75, 100, Importance.CRITICAL),
                             _p("analytical_thinking", 70, 100, Importance.CRITICAL)),
                knowledge=(KnowledgeAreaRequirement("analytical_ability", Importance.HIGH),)),
    )


def demo_career_insights() -> dict:
    """Engine-test fixture insights matching `demo_careers` (see note above).
    The live application's insights come from the Career Knowledge Base."""
    from ..engines.intelligence import CareerInsight, RoadmapSkill

    def rs(name, weeks, diff, gain):
        return RoadmapSkill(name, weeks, diff, gain)

    return {
        "c_ds": CareerInsight(
            "c_ds",
            "Data Scientists turn data into decisions using statistics, programming and machine learning.",
            daily_work=("Explore and clean datasets", "Build and evaluate models",
                        "Communicate insights to stakeholders"),
            responsibilities=("Statistical analysis", "Model development", "Data storytelling"),
            progression=(("Junior Data Scientist", "0-2 yrs"), ("Data Scientist", "2-5 yrs"),
                         ("Senior / Lead", "5-8 yrs"), ("Head of Data", "8+ yrs")),
            salary_entry=70000, salary_senior=160000, currency="$",
            demand=0.9, growth=0.85, automation_risk=0.25, remote_compatibility=0.9,
            required_education=("Bachelor's in a quantitative field", "Bootcamp + portfolio (alt.)"),
            certifications=("AWS ML Specialty", "TensorFlow Developer"),
            related_careers=("c_swe", "c_rs"),
            roadmap=(rs("Python", 8, "moderate", 6), rs("SQL", 4, "easy", 4),
                     rs("Statistics", 6, "moderate", 5), rs("Machine Learning", 10, "hard", 7)),
        ),
        "c_swe": CareerInsight(
            "c_swe",
            "Software Engineers design, build and maintain the systems that power modern products.",
            daily_work=("Write and review code", "Design systems", "Debug and ship features"),
            responsibilities=("Feature development", "Code review", "System design"),
            progression=(("Junior Engineer", "0-2 yrs"), ("Engineer", "2-5 yrs"),
                         ("Senior Engineer", "5-8 yrs"), ("Staff / Lead", "8+ yrs")),
            salary_entry=75000, salary_senior=180000, currency="$",
            demand=0.95, growth=0.8, automation_risk=0.3, remote_compatibility=0.95,
            required_education=("Bachelor's in CS", "Bootcamp + portfolio (alt.)"),
            certifications=("AWS Developer", "Kubernetes (CKA)"),
            related_careers=("c_ds", "c_pm"),
            roadmap=(rs("Python", 8, "moderate", 6), rs("Data Structures", 8, "hard", 6),
                     rs("Web Development", 8, "moderate", 5), rs("System Design", 10, "hard", 6)),
        ),
        "c_ux": CareerInsight(
            "c_ux",
            "UX Designers craft intuitive, human-centred product experiences.",
            daily_work=("Interview users", "Design wireframes & prototypes", "Run usability tests"),
            responsibilities=("User research", "Interaction design", "Design systems"),
            progression=(("Junior Designer", "0-2 yrs"), ("UX Designer", "2-5 yrs"),
                         ("Senior Designer", "5-8 yrs"), ("Design Lead", "8+ yrs")),
            salary_entry=60000, salary_senior=140000, currency="$",
            demand=0.75, growth=0.7, automation_risk=0.35, remote_compatibility=0.85,
            required_education=("Bachelor's in design/HCI", "Portfolio (alt.)"),
            certifications=("Google UX Design", "NN/g UX Certification"),
            related_careers=("c_pm", "c_swe"),
            roadmap=(rs("Design Fundamentals", 6, "easy", 5), rs("Figma", 4, "easy", 4),
                     rs("User Research", 6, "moderate", 5), rs("Prototyping", 6, "moderate", 5)),
        ),
        "c_pm": CareerInsight(
            "c_pm",
            "Product Managers lead product strategy and coordinate teams to deliver value.",
            daily_work=("Prioritize the roadmap", "Talk to users & stakeholders", "Coordinate delivery"),
            responsibilities=("Product strategy", "Stakeholder alignment", "Delivery coordination"),
            progression=(("Associate PM", "0-2 yrs"), ("Product Manager", "2-5 yrs"),
                         ("Senior PM", "5-8 yrs"), ("Director of Product", "8+ yrs")),
            salary_entry=80000, salary_senior=190000, currency="$",
            demand=0.8, growth=0.75, automation_risk=0.2, remote_compatibility=0.8,
            required_education=("Bachelor's degree", "MBA (optional)"),
            certifications=("Pragmatic Institute", "Scrum Product Owner"),
            related_careers=("c_ux", "c_ds"),
            roadmap=(rs("Product Strategy", 6, "moderate", 5), rs("Analytics", 6, "moderate", 5),
                     rs("Communication", 4, "easy", 4), rs("Roadmapping", 4, "moderate", 4)),
        ),
        "c_rs": CareerInsight(
            "c_rs",
            "Research Scientists investigate open questions through rigorous experimentation.",
            daily_work=("Design experiments", "Analyze results", "Publish findings"),
            responsibilities=("Research design", "Experimentation", "Scientific writing"),
            progression=(("PhD Researcher", "0-4 yrs"), ("Research Scientist", "4-8 yrs"),
                         ("Senior Scientist", "8-12 yrs"), ("Principal Scientist", "12+ yrs")),
            salary_entry=75000, salary_senior=200000, currency="$",
            demand=0.7, growth=0.8, automation_risk=0.15, remote_compatibility=0.7,
            required_education=("Master's or PhD", "Strong publication record"),
            certifications=("Domain-specific research credentials",),
            related_careers=("c_ds", "c_swe"),
            roadmap=(rs("Research Methods", 8, "hard", 6), rs("Statistics", 6, "moderate", 5),
                     rs("Python", 8, "moderate", 5), rs("Scientific Writing", 6, "moderate", 5)),
        ),
    }


def build_demo_backend() -> Backend:
    """The live composition: a backend powered entirely by the generated
    Career Knowledge Base (38/39 — one source of truth).

    The knowledge loader validates and loads every career JSON, the repository
    adapts them into ranker aggregates + mentor insights, and the whole set is
    ingested into the Knowledge Platform graph so discovery, the AI coach and
    decision intelligence retrieve from the same layer. The tiny engine
    fixtures above are used only if the knowledge data is absent (stripped
    installs), so the app always boots.
    """
    from ..knowledge.careers import CareerKnowledgeLoader

    loader = CareerKnowledgeLoader()
    repo = loader.build_repository()
    if repo.count() == 0:  # pragma: no cover - stripped-install fallback
        return Backend(careers=demo_careers(), insights=demo_career_insights())

    backend = Backend(
        careers=repo.career_aggregates(),
        insights=repo.insights(),
        career_knowledge=repo,
    )
    loader.ingest_into(backend.knowledge_platform)
    for node in backend.knowledge_graph.list_nodes():
        backend.vector_index.add(
            node.canonical_name, node.description, node.node_type.value)
    return backend
