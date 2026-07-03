"""Dynamic knowledge — Layer 2 facts that are retrieved, cached and refreshed.

Salary, demand, hiring trends, visa rules, scholarships: this information is
never hardcoded per career or per country. A `DynamicFact` is what a
`DynamicKnowledgeProvider` returns for a (subject, fact type, region) query.
Facts carry provenance and an explicit expiry; they live only in the cache and
are re-retrieved when stale — the graph never stores them permanently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from ...domain.common.attributes import Attributes
from ...domain.common.confidence import Confidence
from ...domain.common.provenance import Provenance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DynamicFactType(str, Enum):
    """The volatile fact categories the platform retrieves rather than stores."""

    SALARY = "salary"
    DEMAND = "demand"
    HIRING_TREND = "hiring_trend"
    AI_DISRUPTION = "ai_disruption"
    VISA = "visa"
    SCHOLARSHIP = "scholarship"
    UNIVERSITY = "university"
    COMPANY_HIRING = "company_hiring"
    REMOTE_AVAILABILITY = "remote_availability"
    REGIONAL_DEMAND = "regional_demand"


# Default freshness per fact category (seconds). Configurable per provider/cache.
DEFAULT_FACT_TTL: dict[DynamicFactType, int] = {
    DynamicFactType.SALARY: 7 * 86400,
    DynamicFactType.DEMAND: 7 * 86400,
    DynamicFactType.HIRING_TREND: 86400,
    DynamicFactType.AI_DISRUPTION: 30 * 86400,
    DynamicFactType.VISA: 30 * 86400,
    DynamicFactType.SCHOLARSHIP: 30 * 86400,
    DynamicFactType.UNIVERSITY: 90 * 86400,
    DynamicFactType.COMPANY_HIRING: 86400,
    DynamicFactType.REMOTE_AVAILABILITY: 30 * 86400,
    DynamicFactType.REGIONAL_DEMAND: 7 * 86400,
}


@dataclass(frozen=True, slots=True)
class DynamicFact:
    """One retrieved volatile fact about a subject, optionally region-scoped."""

    subject: str  # canonical entity name, e.g. "Data Scientist"
    fact_type: DynamicFactType
    summary: str
    provenance: Provenance
    region: str = ""  # e.g. "Germany", "IN-AS"; empty = global
    attributes: Attributes = field(default_factory=Attributes)
    confidence: Confidence | None = None
    as_of: datetime = field(default_factory=_utcnow)
    ttl_seconds: int = 7 * 86400

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("DynamicFact.subject must be non-empty")
        if not self.summary.strip():
            raise ValueError("DynamicFact.summary must be non-empty")
        if self.ttl_seconds <= 0:
            raise ValueError("DynamicFact.ttl_seconds must be positive")

    @property
    def expires_at(self) -> datetime:
        return self.as_of + timedelta(seconds=self.ttl_seconds)

    def is_fresh(self, now: datetime) -> bool:
        return now < self.expires_at
