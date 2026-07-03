"""Dynamic knowledge providers — the Layer 2 retrieval ports.

Volatile facts (salary, demand, visas, scholarships) are never stored per
career per country. They are *retrieved* through this port, cached by the
platform, and refreshed on expiry. Salary APIs, job-market APIs and government
statistics APIs plug in behind the same contract; `StaticDynamicKnowledgeProvider`
is the dependency-free in-memory adapter, and `CompositeDynamicKnowledgeProvider`
fans a query out across several providers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.dynamic import DynamicFact, DynamicFactType
from ..models.records import SourceMetadata
from ..normalizers.text import slugify


@runtime_checkable
class DynamicKnowledgeProvider(Protocol):
    """A replaceable origin of volatile facts."""

    def metadata(self) -> SourceMetadata: ...

    def fetch_facts(
        self, subject: str, fact_type: DynamicFactType, region: str = ""
    ) -> tuple[DynamicFact, ...]: ...


class StaticDynamicKnowledgeProvider:
    """An in-memory provider seeded with facts.

    Used for seeds and tests, and as the offline fallback. A real salary/job
    API adapter replaces it behind the same ``fetch_facts`` contract.
    """

    def __init__(self, metadata: SourceMetadata, facts: tuple[DynamicFact, ...] = ()) -> None:
        self._metadata = metadata
        self._facts: dict[tuple[str, str, str], list[DynamicFact]] = {}
        for fact in facts:
            self.add(fact)

    def add(self, fact: DynamicFact) -> None:
        key = (slugify(fact.subject), fact.fact_type.value, slugify(fact.region))
        self._facts.setdefault(key, []).append(fact)

    def metadata(self) -> SourceMetadata:
        return self._metadata

    def fetch_facts(
        self, subject: str, fact_type: DynamicFactType, region: str = ""
    ) -> tuple[DynamicFact, ...]:
        key = (slugify(subject), fact_type.value, slugify(region))
        exact = tuple(self._facts.get(key, ()))
        if exact or not region:
            return exact
        # Fall back to global facts when nothing region-specific is known.
        return tuple(self._facts.get((slugify(subject), fact_type.value, ""), ()))


class CompositeDynamicKnowledgeProvider:
    """Queries every registered provider and concatenates their facts."""

    def __init__(self, metadata: SourceMetadata) -> None:
        self._metadata = metadata
        self._providers: list[DynamicKnowledgeProvider] = []

    def register(self, provider: DynamicKnowledgeProvider) -> None:
        self._providers.append(provider)

    def metadata(self) -> SourceMetadata:
        return self._metadata

    def fetch_facts(
        self, subject: str, fact_type: DynamicFactType, region: str = ""
    ) -> tuple[DynamicFact, ...]:
        facts: list[DynamicFact] = []
        for provider in self._providers:
            facts.extend(provider.fetch_facts(subject, fact_type, region))
        return tuple(facts)
