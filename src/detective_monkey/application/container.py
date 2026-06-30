"""Composition root (400_BACKEND_ARCHITECTURE.md §25 "dependency injection at the
application boundary").

`Backend` wires the engines, in-memory infrastructure adapters and application
services together. This is the only place that knows about concrete adapters;
swapping in real databases/providers happens here, not in the services. Keeping
it dependency-free means the whole platform is runnable and testable out of the box.
"""

from __future__ import annotations

from ..domain.career.career import Career
from ..engines.agent.engine import CareerIntelligenceAgent
from ..engines.agent.types import AgentDependencies
from ..engines.assessment.engine import AssessmentEngine
from ..engines.evidence.engine import EvidenceEngine
from ..engines.explanation.engine import ExplanationEngine
from ..engines.feature_engineering.engine import FeatureEngineeringEngine
from ..engines.recommendation.engine import RecommendationEngine
from ..engines.retrieval.engine import KnowledgeRetrievalEngine
from ..engines.student_intelligence.engine import StudentIntelligenceEngine
from ..infrastructure.event_bus import InMemoryEventBus
from ..infrastructure.platform import InMemoryConfiguration, SystemClock, UuidGenerator
from ..infrastructure.providers import InMemoryVectorIndex, TemplateLLMProvider
from ..infrastructure.repositories import (
    InMemoryCareerCatalogRepository,
    InMemoryEvidenceGraphRepository,
    InMemoryKnowledgeGraphRepository,
    InMemoryMemoryRepository,
    InMemoryProfileRepository,
    InMemoryRecommendationRepository,
    InMemoryStudentRepository,
)
from .services import (
    AskAgentService,
    ExplainRecommendationService,
    GenerateProfileService,
    GenerateRecommendationsService,
    SubmitAssessmentService,
)


class Backend:
    """In-memory composition of the full Detective Monkey backend."""

    def __init__(self, careers: tuple[Career, ...] = (), *, use_llm: bool = True) -> None:
        # Platform services
        self.clock = SystemClock()
        self.ids = UuidGenerator()
        self.config = InMemoryConfiguration()

        # Infrastructure adapters
        self.event_bus = InMemoryEventBus()
        self.students = InMemoryStudentRepository()
        self.profiles = InMemoryProfileRepository()
        self.evidence_graphs = InMemoryEvidenceGraphRepository()
        self.recommendations = InMemoryRecommendationRepository()
        self.memories = InMemoryMemoryRepository()
        self.careers = InMemoryCareerCatalogRepository(careers)
        self.knowledge_graph = InMemoryKnowledgeGraphRepository()
        self.vector_index = InMemoryVectorIndex()

        # Providers
        llm = TemplateLLMProvider() if use_llm else None

        # Engines
        self.assessment_engine = AssessmentEngine()
        self.evidence_engine = EvidenceEngine()
        self.feature_engine = FeatureEngineeringEngine()
        self.intelligence_engine = StudentIntelligenceEngine()
        self.recommendation_engine = RecommendationEngine()
        self.explanation_engine = ExplanationEngine(llm=llm)
        self.retrieval_engine = KnowledgeRetrievalEngine()
        self.agent = CareerIntelligenceAgent(AgentDependencies(
            retrieval_engine=self.retrieval_engine,
            explanation_engine=self.explanation_engine,
            recommendation_engine=self.recommendation_engine,
            llm=llm,
        ))

        # Application services
        self.submit_assessment = SubmitAssessmentService(
            self.students, self.evidence_graphs, self.assessment_engine,
            self.evidence_engine, self.event_bus)
        self.generate_profile = GenerateProfileService(
            self.evidence_graphs, self.profiles, self.feature_engine,
            self.intelligence_engine, self.event_bus)
        self.generate_recommendations = GenerateRecommendationsService(
            self.profiles, self.careers, self.recommendations,
            self.recommendation_engine, self.event_bus)
        self.explain_recommendation = ExplainRecommendationService(
            self.recommendations, self.explanation_engine, self.careers)
        self.ask_agent = AskAgentService(self.agent)
