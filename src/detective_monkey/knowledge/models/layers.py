"""The three knowledge layers of the Knowledge Generation Platform.

Separating knowledge by volatility decides *where it lives*: core knowledge is
stored permanently in the Knowledge Graph, dynamic knowledge is retrieved and
cached with an expiry, personalized intelligence is generated per request and
never persisted as truth.
"""

from __future__ import annotations

from enum import Enum


class KnowledgeLayer(str, Enum):
    """How volatile a piece of knowledge is, and therefore where it lives."""

    CORE = "core"  # stable: careers, skills, relationships — stored permanently
    DYNAMIC = "dynamic"  # volatile: salary, demand, visas — retrieved + cached
    PERSONALIZED = "personalized"  # per-user reasoning — generated, never stored
