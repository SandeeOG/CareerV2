"""Knowledge-query intent detection.

The first stage of the retrieval pipeline. Intent decides which retrieval
strategies run (graph search, graph expansion, dynamic facts) and which fact
types are worth fetching. Deterministic keyword rules — replaceable behind the
same ``classify`` signature without touching the pipeline.
"""

from __future__ import annotations

import re
from enum import Enum

from ..models.dynamic import DynamicFactType


class KnowledgeIntent(str, Enum):
    DISCOVERY = "discovery"  # "careers using mathematics", "remote careers"
    FACT = "fact"  # "what is the salary of ...", "demand for ..."
    REGIONAL = "regional"  # "careers in Germany", "... in Assam"
    COMPARISON = "comparison"  # "data science vs software engineering"
    RELATIONSHIP = "relationship"  # "what skills does ... need"
    LEARNING_PATH = "learning_path"  # "how do I become ..."
    GENERAL = "general"


# Ordered rules; first match wins (deterministic).
_RULES: tuple[tuple[KnowledgeIntent, tuple[str, ...]], ...] = (
    (KnowledgeIntent.COMPARISON, (" vs ", " versus ", "compare", "better than",
                                  "or should i")),
    (KnowledgeIntent.LEARNING_PATH, ("how do i become", "how to become",
                                     "learning path", "roadmap", "path to")),
    (KnowledgeIntent.FACT, ("salary", "salaries", "pay", "earn", "demand",
                            "hiring", "visa", "scholarship", "remote work",
                            "ai disruption", "automation risk")),
    (KnowledgeIntent.RELATIONSHIP, ("what skills", "which skills", "requirements",
                                    "need to know", "prerequisites")),
    (KnowledgeIntent.REGIONAL, (" in ", "near me", "relocat", "abroad", "cities")),
    (KnowledgeIntent.DISCOVERY, ("careers", "career options", "jobs for", "explore",
                                 "show me", "which career", "what career")),
)

# Which dynamic fact types each query keyword pulls in.
_FACT_KEYWORDS: tuple[tuple[DynamicFactType, tuple[str, ...]], ...] = (
    (DynamicFactType.SALARY, ("salary", "salaries", "pay", "earn", "income")),
    (DynamicFactType.DEMAND, ("demand", "opportunities", "job market", "openings")),
    (DynamicFactType.HIRING_TREND, ("hiring", "trend")),
    (DynamicFactType.AI_DISRUPTION, ("ai disruption", "automation", "ai risk",
                                     "replaced by ai")),
    (DynamicFactType.VISA, ("visa", "work permit", "immigration")),
    (DynamicFactType.SCHOLARSHIP, ("scholarship", "funding", "grant")),
    (DynamicFactType.UNIVERSITY, ("university", "universities", "college")),
    (DynamicFactType.REMOTE_AVAILABILITY, ("remote",)),
    (DynamicFactType.REGIONAL_DEMAND, ("relocat", "cities", "region", "local")),
)


def classify(query: str) -> KnowledgeIntent:
    q = f" {query.lower()} "
    for intent, keywords in _RULES:
        if any(k in q for k in keywords):
            return intent
    return KnowledgeIntent.GENERAL


def requested_fact_types(query: str) -> tuple[DynamicFactType, ...]:
    q = query.lower()
    out = []
    for fact_type, keywords in _FACT_KEYWORDS:
        if any(k in q for k in keywords):
            out.append(fact_type)
    return tuple(out)


def extract_region(query: str, known_regions: tuple[str, ...]) -> str:
    """Match a known country/region name inside the query (longest wins)."""
    q = query.lower()
    best = ""
    for region in known_regions:
        r = region.lower()
        if r and re.search(rf"\b{re.escape(r)}\b", q) and len(r) > len(best):
            best = region
    return best
