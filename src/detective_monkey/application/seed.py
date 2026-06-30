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
from ..domain.knowledge_graph.node import Node, NodeId
from ..domain.knowledge_graph.ontology import NodeType
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


def demo_knowledge_nodes() -> tuple[Node, ...]:
    careers = [
        ("n_ds", "Data Scientist", "Analyzes data using statistics and machine learning to drive decisions.", ("data", "analytics", "ml")),
        ("n_swe", "Software Engineer", "Designs and builds software systems and applications.", ("programming", "engineering")),
        ("n_ux", "UX Designer", "Designs intuitive, human-centred product experiences.", ("design", "creativity")),
        ("n_pm", "Product Manager", "Leads product strategy and coordinates teams to ship value.", ("leadership", "strategy")),
        ("n_rs", "Research Scientist", "Investigates open questions through rigorous research.", ("research", "science")),
    ]
    skills = [
        ("n_py", "Python", "A versatile programming language used across data and software.", ("programming",)),
        ("n_stats", "Statistics", "The science of learning from data.", ("analytics",)),
    ]
    nodes = [
        Node(NodeId(i), NodeType.CAREER, name, _V1, description=desc, semantic_tags=tags)
        for i, name, desc, tags in careers
    ]
    nodes += [
        Node(NodeId(i), NodeType.SKILL, name, _V1, description=desc, semantic_tags=tags)
        for i, name, desc, tags in skills
    ]
    return tuple(nodes)


def build_demo_backend() -> Backend:
    """A fully-seeded, in-memory backend ready to serve the complete journey."""
    backend = Backend(careers=demo_careers())
    for node in demo_knowledge_nodes():
        backend.knowledge_graph.add_node(node)
        backend.vector_index.add(node.canonical_name, node.description, node.node_type.value)
    return backend
