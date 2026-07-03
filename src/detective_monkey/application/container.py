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
from ..engines.intelligence import IntelligenceEngine
from ..engines.recommendation.engine import RecommendationEngine
from ..engines.discovery import DiscoveryEngine
from ..engines.retrieval.engine import KnowledgeRetrievalEngine
from ..engines.student_evidence import StudentEvidenceEngine
from ..engines.student_intelligence.engine import StudentIntelligenceEngine
from ..infrastructure.event_bus import InMemoryEventBus
from ..infrastructure.platform import EnvConfiguration, SystemClock, UuidGenerator
from ..infrastructure.providers import GeminiProvider, InMemoryVectorIndex, TemplateLLMProvider
from ..knowledge import KnowledgePlatform
from ..infrastructure.repositories import (
    InMemoryCareerCatalogRepository,
    InMemoryEvidenceGraphRepository,
    InMemoryEvidenceProfileRepository,
    InMemoryExperimentRepository,
    InMemoryIntelligenceProfileRepository,
    InMemoryKnowledgeGraphRepository,
    InMemoryMemoryRepository,
    InMemoryMentorMemory,
    InMemoryProfileRepository,
    InMemoryRecommendationRepository,
    InMemoryStudentRepository,
)
from .discovery_service import DiscoveryApplicationService
from .evidence_service import EvidenceApplicationService
from .intelligence_service import IntelligenceApplicationService
from .services import (
    AskAgentService,
    ExplainRecommendationService,
    GenerateProfileService,
    GenerateRecommendationsService,
    SubmitAssessmentService,
)


class Backend:
    """In-memory composition of the full Detective Monkey backend."""

    def __init__(self, careers: tuple[Career, ...] = (), *, use_llm: bool = True,
                 insights: dict | None = None, llm: object | None = None,
                 career_knowledge: object | None = None,
                 db_path: str | None = None) -> None:
        # Platform services
        self.clock = SystemClock()
        self.ids = UuidGenerator()
        self.config = EnvConfiguration()

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
        self.intelligence_profiles = InMemoryIntelligenceProfileRepository()
        # The two aggregates whose history *is* the product persist to SQLite
        # when a db_path is configured; derived state stays in memory and is
        # rebuilt deterministically on first touch (evidence.ensure_ready).
        if db_path:
            from ..infrastructure.sqlite_store import (
                SqliteEvidenceProfileRepository,
                SqliteExperimentRepository,
            )
            self.evidence_profiles = SqliteEvidenceProfileRepository(db_path)
            self.experiments = SqliteExperimentRepository(db_path)
        else:
            self.evidence_profiles = InMemoryEvidenceProfileRepository()
            self.experiments = InMemoryExperimentRepository()
        self.mentor_memory = InMemoryMentorMemory()
        self.career_insights = insights or {}
        # The Career Knowledge Repository — when provided (the normal case,
        # wired by `seed.build_demo_backend`), it is the application's single
        # source of career truth (38/39): `careers` and `insights` above are
        # its adapter views, and the Explore Careers API reads it directly.
        self.career_knowledge = career_knowledge

        # Providers — explicit `llm` wins; otherwise auto-detect a configured
        # provider from the environment (409 §16 "providers are selected through
        # configuration"); fall back to the deterministic template so the app
        # always runs without any external dependency.
        if llm is not None:
            pass  # explicit injection (e.g. tests, or a future Anthropic/OpenAI provider)
        elif not use_llm:
            llm = None
        else:
            gemini_key = self.config.get("GEMINI_API_KEY")
            if gemini_key:
                gemini_model = self.config.get("GEMINI_MODEL", "gemini-2.0-flash")
                llm = GeminiProvider(gemini_key, model=gemini_model)
            else:
                llm = TemplateLLMProvider()

        # Engines
        self.assessment_engine = AssessmentEngine()
        self.evidence_engine = EvidenceEngine()
        self.feature_engine = FeatureEngineeringEngine()
        self.intelligence_engine = StudentIntelligenceEngine()
        self.reasoning_engine = IntelligenceEngine()  # the single reasoning component
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

        # Evidence-derived career affinities shared between the Evidence and
        # Intelligence services (student id → {career id: ranking bonus}).
        self.career_affinities: dict = {}

        # Intelligence Layer — the single reasoning component for the live app.
        self.intelligence = IntelligenceApplicationService(
            self.assessment_engine, self.reasoning_engine, self.careers,
            self.students, self.intelligence_profiles, self.event_bus,
            insights=self.career_insights, memory=self.mentor_memory,
            affinities=self.career_affinities)

        # Student Evidence Engine — the primary source of student information.
        # AI (whatever provider is configured) is used only for feature
        # extraction from open-ended answers; everything else is deterministic.
        self.student_evidence_engine = StudentEvidenceEngine()
        self.evidence = EvidenceApplicationService(
            self.student_evidence_engine, self.evidence_profiles,
            self.intelligence, career_knowledge=self.career_knowledge, llm=llm,
            affinities=self.career_affinities)

        # Discovery loop — hypotheses → calibrated experiments → reflection →
        # experience evidence → recalibration. Deterministic design; the LLM
        # only polishes wording and extracts reflection features.
        self.discovery_engine = DiscoveryEngine(llm=llm)
        self.discovery = DiscoveryApplicationService(
            self.discovery_engine, self.experiments,
            self.student_evidence_engine, self.evidence_profiles,
            self.evidence, self.intelligence, self.career_knowledge, self.ids)
        self.evidence.attach_discovery(self.discovery)

        # Knowledge Generation Platform — the single source of truth for career
        # knowledge. Shares the canonical Knowledge Graph repository, event bus,
        # clock and (optional) LLM; knowledge sources and dynamic providers are
        # registered on it by seeds/deployment code.
        self.knowledge_platform = KnowledgePlatform(
            self.knowledge_graph,
            clock=self.clock,
            llm=llm,
            publisher=self.event_bus,
        )
