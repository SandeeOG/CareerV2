"""End-to-end backend (P4) test over in-memory infrastructure (P3).

Exercises the full application flow through services — submit assessment ->
generate profile -> generate recommendations -> explain -> ask agent — asserting
persistence, event publication, and standardized results at each step.
"""

from __future__ import annotations

from detective_monkey.application.container import Backend
from detective_monkey.domain.career import Career, CareerIdentity, PersonalityRequirement
from detective_monkey.domain.common import (
    Confidence, Importance, Score, ScoreRange, UnitInterval, Version,
)
from detective_monkey.domain.common.events import EventName
from detective_monkey.domain.common.identifiers import (
    CareerId, RecommendationId, SkillId, StudentId,
)
from detective_monkey.domain.recommendation import Dimension, WeightConfiguration
from detective_monkey.domain.skills import CareerSkill, StudentSkill
from detective_monkey.domain.skills.student_skill import ProficiencyLevel
from detective_monkey.engines.agent.types import AgentInput
from detective_monkey.engines.assessment import (
    AssessmentDefinition, AssessmentInput, AssessmentSubmission, ItemResponse,
    Question, Section,
)
from detective_monkey.engines.feature_engineering import (
    FeatureCategory, FeatureDefinition, FeatureType,
)
from detective_monkey.engines.retrieval import RetrievalInput
from detective_monkey.engines.student_intelligence import (
    AggregationRule, ConstructSource, DerivedFeatureSpec, ReasoningConfig,
)

SID = StudentId("studentx")


def _careers():
    py = SkillId("skill_python")
    ds = Career(
        CareerIdentity(CareerId("c_ds"), "Data Scientist", "data-scientist"), Version(2),
        skills=(CareerSkill(CareerId("c_ds"), py, Importance.CRITICAL,
                            ProficiencyLevel.INTERMEDIATE, ProficiencyLevel.ADVANCED),),
        personality=(PersonalityRequirement("analytical_thinking",
                                            ScoreRange(Score(70), Score(100)),
                                            Importance.CRITICAL),),
    )
    artist = Career(
        CareerIdentity(CareerId("c_art"), "Visual Artist", "visual-artist"), Version(1),
        personality=(PersonalityRequirement("creativity",
                                            ScoreRange(Score(70), Score(100)),
                                            Importance.CRITICAL),),
    )
    return (ds, artist)


def _assessment_input():
    defn = AssessmentDefinition(
        id="big5", version=Version(1),
        sections=(Section("s1", "Reasoning", (
            Question("q1", "analytical_thinking", scale_min=1, scale_max=5),
            Question("q2", "analytical_thinking", reverse_scored=True, scale_min=1, scale_max=5),
            Question("q3", "curiosity", scale_min=1, scale_max=5),
        )),),
    )
    sub = AssessmentSubmission(SID, "big5", Version(1), (
        ItemResponse("q1", 5.0, 1200), ItemResponse("q2", 1.0, 1300),
        ItemResponse("q3", 4.0, 1100),
    ))
    return AssessmentInput(defn, sub)


def _feature_defs():
    return (
        FeatureDefinition("f_analytical", "Analytical", FeatureCategory.PSYCHOMETRIC,
                          FeatureType.PERCENTAGE, "evidence_mean", Version(1),
                          inputs=("analytical_thinking",)),
        FeatureDefinition("f_curiosity", "Curiosity", FeatureCategory.PSYCHOMETRIC,
                          FeatureType.PERCENTAGE, "evidence_mean", Version(1),
                          inputs=("curiosity",)),
    )


def _reasoning_config():
    return ReasoningConfig(
        Version(1),
        construct_sources=(ConstructSource("analytical_thinking", "f_analytical"),
                           ConstructSource("curiosity", "f_curiosity")),
        domain_rules=(AggregationRule("analytical_ability",
                                      (("analytical_thinking", 0.7), ("curiosity", 0.3))),),
        derived_features=(DerivedFeatureSpec("analytical_strength", "f_analytical"),),
    )


def _weights():
    return WeightConfiguration(Version(1), weights=(
        (Dimension.PSYCHOLOGICAL, UnitInterval(0.6)),
        (Dimension.SKILL, UnitInterval(0.4)),
    ))


def test_backend_end_to_end():
    backend = Backend(careers=_careers())

    # Subscribe a counter to verify events are published after each step.
    published: list[str] = []
    for name in (EventName.STUDENT_PROFILE_GENERATED, EventName.RECOMMENDATION_GENERATED,
                 EventName.EVIDENCE_COLLECTED):
        backend.event_bus.subscribe(name, "counter", lambda e: published.append(e.name.value))

    # 1. Assessment -> Evidence (persisted)
    a = backend.submit_assessment.execute(_assessment_input())
    assert a.success, a.errors
    assert a.data.evidence_count >= 2
    assert backend.evidence_graphs.get(SID) is not None

    # 2. Profile (persisted, becomes active)
    p = backend.generate_profile.execute(SID, _feature_defs(), _reasoning_config())
    assert p.success, p.errors
    assert backend.profiles.get_active(SID) is not None
    assert dict(p.data.constructs)["analytical_thinking"] == 100.0

    # 3. Recommendations (persisted, ranked).
    # A known StudentSkill requires evidence (13 INV-04).
    from detective_monkey.domain.common.identifiers import EvidenceId
    skills = (StudentSkill(SID, SkillId("skill_python"), ProficiencyLevel.INTERMEDIATE,
                           Confidence.of(0.8), evidence=(EvidenceId("ev_seed"),)),)
    r = backend.generate_recommendations.execute(SID, _weights(), student_skills=skills)
    assert r.success, r.errors
    assert r.data.recommendations
    top = r.data.recommendations[0]
    assert top.career_id == "c_ds"  # analytical student -> Data Scientist
    assert backend.recommendations.list_for_student(SID)

    # 4. Explanation
    e = backend.explain_recommendation.execute(RecommendationId(top.recommendation_id))
    assert e.success, e.errors
    assert "Data Scientist" in e.data.content

    # 5. Agent (exploration)
    from detective_monkey.domain.knowledge_graph import Node, NodeType
    from detective_monkey.domain.knowledge_graph.node import NodeId
    nodes = (Node(NodeId("n_ds"), NodeType.CAREER, "Data Scientist", Version(1),
                  description="Analyzes data"),)
    ag = backend.ask_agent.execute(AgentInput(
        "Tell me about data scientist",
        retrieval_input=RetrievalInput(query="Tell me about data scientist",
                                       knowledge_nodes=nodes)))
    assert ag.success
    assert "Data Scientist" in ag.data.response

    # Events were published after the relevant steps.
    assert EventName.STUDENT_PROFILE_GENERATED.value in published
    assert EventName.RECOMMENDATION_GENERATED.value in published
    metrics = backend.event_bus.metrics()
    assert metrics["published"] > 0 and metrics["delivered"] > 0


def test_generate_profile_without_evidence_returns_not_found():
    backend = Backend(careers=_careers())
    result = backend.generate_profile.execute(
        StudentId("ghost"), _feature_defs(), _reasoning_config())
    assert not result.success
    assert result.errors[0].code.value == "NOT_FOUND"
