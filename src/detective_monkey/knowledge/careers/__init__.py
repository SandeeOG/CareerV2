"""The v1 Career Knowledge Base: ~300 broad career paths in 16 industries.

Generated (never hand-written), schema-validated JSON profiles under
``data/`` plus the loader and repository that make them the application's
single source of career truth. See ``schema.py`` for the canonical schema and
``tools/generate_career_knowledge.py`` for the generation pipeline.
"""

from .loader import CareerKnowledgeLoader, LoadReport
from .repository import CareerKnowledgeRepository, CareerSearchFilters
from .schema import CareerProfile, IndustryProfile

__all__ = [
    "CareerKnowledgeLoader",
    "CareerKnowledgeRepository",
    "CareerProfile",
    "CareerSearchFilters",
    "IndustryProfile",
    "LoadReport",
]
