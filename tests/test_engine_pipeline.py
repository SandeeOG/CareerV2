"""End-to-end Phase 2 pipeline test (18 §5 intelligence pipeline).

Wires the full deterministic chain — assessment -> evidence -> features -> SIP ->
recommendation -> explanation -> evaluation — plus retrieval and the agent, and
asserts the documented behaviour at each stage.
"""

from __future__ import annotations

import pytest

from detective_monkey.contracts import EngineRequest, EngineStatus, IntelligenceContext
from detective_monkey.domain.career import (
    Career,
    CareerIdentity,
    KnowledgeAreaRequirement,
    PersonalityRequirement,
)
from detective_monkey.domain.common import (
    Confidence,
    Importance,
    Score,
    ScoreRange,
    UnitInterval,
    Version,
)
from detective_monkey.domain.common.identifiers import CareerId, SkillId, StudentId
from detective_monkey.domain.recommendation import Dimension, WeightConfiguration
from detective_monkey.domain.recommendation.contracts import RecommendationRequest
from detective_monkey.domain.skills import CareerSkill, StudentSkill
from detective_monkey.domain.skills.student_skill import ProficiencyLevel
from detective_monkey.engines.assessment import (
    AssessmentDefinition,
    AssessmentEngine,
    AssessmentInput,
    AssessmentSubmission,
    ItemResponse,
    Question,
    Section,
)
from detective_monkey.engines.evidence import EvidenceEngine, EvidenceInput
from detective_monkey.engines.explanation import ExplanationEngine, ExplanationInput
from detective_monkey.engines.evaluation import EvaluationEngine, EvaluationInput
from detective_monkey.engines.feature_engineering import (
    FeatureCategory,
    FeatureDefinition,
    FeatureEngineeringEngine,
    FeatureEngineeringInput,
    FeatureType,
)
from detective_monkey.engines.recommendation import RecommendationEngine
from detective_monkey.engines.student_intelligence import (
    AggregationRule,
    ConstructSource,
    DerivedFeatureSpec,
    ReasoningConfig,
    StudentIntelligenceEngine,
    StudentIntelligenceInput,
)

SID = StudentId("student_x")
CTX = IntelligenceContext(student_id="student_x")


def _assessment_result():
    defn = AssessmentDefinition(
        id="big5", version=Version(1),
        sections=(Section("s1", "Reasoning", (
            Question("q1", "analytical_thinking", scale_min=1, scale_max=5),
            Question("q2", "analytical_thinking", reverse_scored=True, scale_min=1, scale_max=5),
            Question("q3", "curiosity", scale_min=1, scale_max=5),
        )),),
    )
    sub = AssessmentSubmission(SID, "big5", Version(1), (
        ItemResponse("q1", 5.0, 1200),
        ItemResponse("q2", 1.0, 1500),
        ItemResponse("q3", 4.0, 900),
    ))
    return AssessmentEngine().execute(EngineRequest(CTX, AssessmentInput(defn, sub)))


def test_full_pipeline_produces_explained_recommendation():
    # 1. Assessment -> evidence
    a = _assessment_result()
    assert a.ok
    assessment_evidence = a.result.evidence

    # 2. Evidence Engine -> evidence graph
    eg = EvidenceEngine().execute(
        EngineRequest(CTX, EvidenceInput(SID, existing_evidence=assessment_evidence))
    )
    assert eg.ok
    graph = eg.result
    assert "analytical_thinking" in graph.subjects()

    # 3. Feature engineering
    defs = (
        FeatureDefinition("f_analytical", "Analytical", FeatureCategory.PSYCHOMETRIC,
                          FeatureType.PERCENTAGE, "evidence_mean", Version(1),
                          inputs=("analytical_thinking",)),
        FeatureDefinition("f_curiosity", "Curiosity", FeatureCategory.PSYCHOMETRIC,
                          FeatureType.PERCENTAGE, "evidence_mean", Version(1),
                          inputs=("curiosity",)),
    )
    fe = FeatureEngineeringEngine().execute(
        EngineRequest(CTX, FeatureEngineeringInput(graph, defs))
    )
    assert fe.ok
    feature_set = fe.result

    # 4. Student Intelligence -> SIP
    cfg = ReasoningConfig(
        Version(1),
        construct_sources=(ConstructSource("analytical_thinking", "f_analytical"),
                           ConstructSource("curiosity", "f_curiosity")),
        domain_rules=(AggregationRule("analytical_ability",
                                      (("analytical_thinking", 0.7), ("curiosity", 0.3))),),
        derived_features=(DerivedFeatureSpec("analytical_strength", "f_analytical"),),
    )
    si = StudentIntelligenceEngine().execute(
        EngineRequest(CTX, StudentIntelligenceInput(SID, graph, feature_set, cfg))
    )
    assert si.ok
    profile = si.result
    assert profile.construct("analytical_thinking").score.value == pytest.approx(100.0)

    # 5. Recommendation
    py = SkillId("skill_python")
    ds = Career(
        CareerIdentity(CareerId("c_ds"), "Data Scientist", "data-scientist"), Version(3),
        skills=(CareerSkill(CareerId("c_ds"), py, Importance.CRITICAL,
                            ProficiencyLevel.INTERMEDIATE, ProficiencyLevel.ADVANCED),),
        personality=(PersonalityRequirement("analytical_thinking",
                                            ScoreRange(Score(70), Score(100)),
                                            Importance.CRITICAL),),
        knowledge_areas=(KnowledgeAreaRequirement("analytical_ability", Importance.HIGH),),
    )
    artist = Career(
        CareerIdentity(CareerId("c_art"), "Visual Artist", "visual-artist"), Version(1),
        personality=(PersonalityRequirement("creativity",
                                            ScoreRange(Score(70), Score(100)),
                                            Importance.CRITICAL),),
    )
    weights = WeightConfiguration(Version(1), weights=(
        (Dimension.PSYCHOLOGICAL, UnitInterval(0.5)),
        (Dimension.SKILL, UnitInterval(0.3)),
        (Dimension.KNOWLEDGE, UnitInterval(0.2)),
    ))
    student_skills = (StudentSkill(SID, py, ProficiencyLevel.INTERMEDIATE,
                                   Confidence.of(0.8), tuple(profile.evidence[:1] or ())),)
    req = RecommendationRequest(profile=profile, careers=(ds, artist), weights=weights,
                                student_skills=student_skills)
    rr = RecommendationEngine().execute(EngineRequest(CTX, req))
    assert rr.ok and rr.result.recommendations
    top = rr.result.recommendations[0]
    # Data Scientist (analytical) should outrank Visual Artist (creativity) for this student.
    assert top.career_id.value == "c_ds"
    assert top.evidence  # INV-04
    assert any(g.skill_id.value == "skill_python" for g in top.skill_gaps)

    # 6. Explanation
    ex = ExplanationEngine().execute(
        EngineRequest(CTX, ExplanationInput(top, "Data Scientist"))
    )
    assert ex.ok
    assert "Data Scientist" in ex.result.explanation.content
    assert ex.result.explanation_object.suggested_improvements  # has gaps -> improvements

    # 7. Evaluation across the stack
    eval_resp = EvaluationEngine().execute(EngineRequest(CTX, EvaluationInput(
        evidence_graph=graph,
        feature_set=feature_set,
        profile=profile,
        recommendation_response=rr.result,
        explanation_object=ex.result.explanation_object,
    )))
    assert eval_resp.ok
    rec_group = eval_resp.result.group("recommendations")
    assert rec_group is not None
    assert rec_group.get("evidence_presence_rate").value == pytest.approx(1.0)


def test_pipeline_is_deterministic():
    """Identical inputs produce identical recommendations (16/25 INV)."""
    a1 = _assessment_result()
    a2 = _assessment_result()
    ids1 = [e.id.value for e in a1.result.evidence]
    ids2 = [e.id.value for e in a2.result.evidence]
    assert ids1 == ids2
    # The construct values are identical too.
    v1 = [e.metadata.get("value") for e in a1.result.evidence]
    v2 = [e.metadata.get("value") for e in a2.result.evidence]
    assert v1 == v2
