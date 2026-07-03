"""KnowledgePlatform — the composition facade of the knowledge platform.

One object that wires sources, normalization, validation, generation, the
graph, the cache, dynamic providers and the retrieval pipeline together, so
the application container (and tests) integrate the whole platform with a
single constructor call. Every collaborator remains individually replaceable:
pass your own canonicalizer, validation pipeline, providers or LLM.

Extension points (interfaces only — no implementation required today):
- new `KnowledgeSource`s (government APIs, LinkedIn, Coursera, universities)
  register on ``sources``;
- new `DynamicKnowledgeProvider`s (salary APIs, job-market APIs) register on
  ``dynamic_providers``;
- a graph database replaces the `KnowledgeGraphRepository` adapter;
- a vector store slots in behind the retrieval pipeline's traversal search.
"""

from __future__ import annotations

from ...application.ports import Clock, EventPublisher, KnowledgeGraphRepository
from ...domain.common.provenance import SourceType
from ...domain.common.scores import UnitInterval
from ..cache.cache import KnowledgeCache
from ..generators.llm import LLMPort
from ..graph.traversal import GraphTraversal
from ..models.records import SourceMetadata
from ..normalizers.canonicalizer import Canonicalizer
from ..retrieval.pipeline import KnowledgeAnswer, KnowledgeRetrievalPipeline
from ..sources.base import SourceRegistry
from ..sources.dynamic import CompositeDynamicKnowledgeProvider, DynamicKnowledgeProvider
from ..validators.pipeline import ValidationPipeline
from .decision import DecisionSupportService
from .discovery import CareerDiscoveryService
from .generation import GenerationReport, KnowledgeGenerationService
from .regional import RegionalIntelligenceService


class KnowledgePlatform:
    """The single entry point to the Knowledge Generation Platform."""

    def __init__(
        self,
        graph: KnowledgeGraphRepository,
        *,
        clock: Clock | None = None,
        llm: LLMPort | None = None,
        publisher: EventPublisher | None = None,
        canonicalizer: Canonicalizer | None = None,
        validation: ValidationPipeline | None = None,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.graph = graph
        self.sources = SourceRegistry()
        self.dynamic_providers = CompositeDynamicKnowledgeProvider(
            SourceMetadata(
                source_id="dynamic_composite",
                name="Composite dynamic knowledge provider",
                source_type=SourceType.EXTERNAL_INTEGRATION,
                reliability=UnitInterval(0.5),
            )
        )
        self.cache = KnowledgeCache(clock, cache_ttl_seconds)
        self.canonicalizer = canonicalizer or Canonicalizer()
        self.validation = validation or ValidationPipeline()
        self.traversal = GraphTraversal(graph)

        self.generation = KnowledgeGenerationService(
            self.sources,
            graph,
            canonicalizer=self.canonicalizer,
            validation=self.validation,
            llm=llm,
            publisher=publisher,
        )
        self.retrieval = KnowledgeRetrievalPipeline(
            self.traversal, self.dynamic_providers, self.cache, llm
        )
        self.discovery = CareerDiscoveryService(
            self.traversal, self.dynamic_providers, llm
        )
        self.decisions = DecisionSupportService(
            self.traversal, self.dynamic_providers, self.cache, llm
        )
        self.regional = RegionalIntelligenceService(
            self.traversal, self.dynamic_providers, self.cache, llm
        )

    # -- convenience entry points ------------------------------------------------

    def register_dynamic_provider(self, provider: DynamicKnowledgeProvider) -> None:
        self.dynamic_providers.register(provider)

    def generate(self) -> GenerationReport:
        """One full generation run over every registered source.

        Designed to be scheduled as a background job; it must never run on a
        user-facing request path.
        """
        return self.generation.ingest_all()

    def ask(self, query: str, student_context: str = "") -> KnowledgeAnswer:
        """Answer a knowledge question through the retrieval pipeline."""
        return self.retrieval.answer(query, student_context)
