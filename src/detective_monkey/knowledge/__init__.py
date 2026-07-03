"""Knowledge Generation Platform.

Detective Monkey never becomes a manually maintained career database. Instead
this package continuously *generates, normalizes, validates, enriches and
stores* the Career Knowledge Base, and serves it back through a retrieval-first
pipeline. It is the single source of truth for career knowledge, powering the
Recommendation Engine, Intelligence Engine, Career Discovery, AI Mentor,
Decision Intelligence and Roadmaps.

Knowledge is split into three layers (`models.layers.KnowledgeLayer`):

- **Core** — stable canonical knowledge (careers, skills, relationships).
  Generated once, validated, stored permanently in the Knowledge Graph.
- **Dynamic** — volatile facts (salary, demand, visas). Never hardcoded:
  retrieved through `DynamicKnowledgeProvider` ports, cached with a TTL.
- **Personalized** — generated per request from profile + core + dynamic
  knowledge and LLM reasoning; never stored as permanent truth.

The LLM is used only to *generate* (behind validation) and to *explain*
retrieved knowledge — it never invents factual career data and it is never the
retrieval mechanism. The whole package keeps the platform rule of zero runtime
dependencies (ADR 0001): every external capability is a replaceable port.
"""

from .services.decision import DecisionSupportService
from .services.discovery import CareerDiscoveryService
from .services.generation import KnowledgeGenerationService
from .services.platform import KnowledgePlatform
from .services.regional import RegionalIntelligenceService

__all__ = [
    "CareerDiscoveryService",
    "DecisionSupportService",
    "KnowledgeGenerationService",
    "KnowledgePlatform",
    "RegionalIntelligenceService",
]
