"""Knowledge platform services: generation, discovery, decisions, regional."""

from .decision import DecisionReport, DecisionSupportService
from .discovery import CareerDiscoveryService, DiscoveryResult, extract_facets
from .generation import GenerationReport, KnowledgeGenerationService
from .platform import KnowledgePlatform
from .regional import RegionalAdvice, RegionalIntelligenceService

__all__ = [
    "CareerDiscoveryService",
    "DecisionReport",
    "DecisionSupportService",
    "DiscoveryResult",
    "GenerationReport",
    "KnowledgeGenerationService",
    "KnowledgePlatform",
    "RegionalAdvice",
    "RegionalIntelligenceService",
    "extract_facets",
]
