"""RegionalIntelligenceService — generated regional advice, cached, never stored.

The platform never materializes Career x Country x District records. Given a
career and a student location it *retrieves* the regional dynamic facts
(regional demand, salaries, remote availability, universities), generates the
advice, and caches the result with an expiry. Adding a new country requires a
dynamic provider that can answer for it — no new database records.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.confidence import Confidence
from ...domain.knowledge_graph.node import Node
from ..cache.cache import KnowledgeCache
from ..generators.llm import LLMPort
from ..graph.traversal import GraphTraversal
from ..models.dynamic import DynamicFact, DynamicFactType
from ..normalizers.text import slugify
from ..prompts.templates import regional_prompt
from ..sources.dynamic import DynamicKnowledgeProvider

_REGIONAL_FACT_TYPES = (
    DynamicFactType.REGIONAL_DEMAND,
    DynamicFactType.SALARY,
    DynamicFactType.DEMAND,
    DynamicFactType.REMOTE_AVAILABILITY,
    DynamicFactType.UNIVERSITY,
    DynamicFactType.SCHOLARSHIP,
)
_ADVICE_TTL = 7 * 86400


@dataclass(frozen=True, slots=True)
class RegionalAdvice:
    career: str
    location: str
    advice: str
    facts: tuple[DynamicFact, ...] = field(default_factory=tuple)
    confidence: Confidence | None = None
    generated_by_llm: bool = False


class RegionalIntelligenceService:
    """Career + location → generated, cached regional guidance."""

    def __init__(
        self,
        traversal: GraphTraversal,
        dynamic_provider: DynamicKnowledgeProvider | None = None,
        cache: KnowledgeCache | None = None,
        llm: LLMPort | None = None,
    ) -> None:
        self._traversal = traversal
        self._dynamic = dynamic_provider
        self._cache = cache or KnowledgeCache()
        self._llm = llm

    def advise(self, career_name: str, location: str) -> RegionalAdvice:
        key = KnowledgeCache.key("regional", slugify(career_name), slugify(location))
        return self._cache.get_or_compute(
            key, lambda: self._advise(career_name, location), ttl_seconds=_ADVICE_TTL
        )

    def _advise(self, career_name: str, location: str) -> RegionalAdvice:
        career = self._traversal.find_by_name(career_name)
        subject = career.canonical_name if career else career_name

        facts: list[DynamicFact] = []
        if self._dynamic is not None:
            for fact_type in _REGIONAL_FACT_TYPES:
                facts.extend(self._dynamic.fetch_facts(subject, fact_type, location))

        advice, used_llm = self._generate(career, subject, location, tuple(facts))
        coverage = min(1.0, len(facts) / 4)
        return RegionalAdvice(
            career=subject,
            location=location,
            advice=advice,
            facts=tuple(facts),
            confidence=Confidence.of(round(0.2 + 0.7 * coverage, 4)),
            generated_by_llm=used_llm,
        )

    def _generate(
        self,
        career: Node | None,
        subject: str,
        location: str,
        facts: tuple[DynamicFact, ...],
    ) -> tuple[str, bool]:
        if self._llm is not None and career is not None and facts:
            generated = self._llm.generate(
                regional_prompt(career, location, facts)
            ).strip()
            if generated:
                return generated, True
        if not facts:
            return (
                f"No regional data is currently available for {subject} around "
                f"{location}. The platform reports unknown rather than inventing "
                "regional statistics; global guidance for the career still applies.",
                False,
            )
        lines = [f"Regional picture for {subject} near {location}:"]
        lines.extend(
            f"- [{f.fact_type.value}] {f.summary} (as of {f.as_of.date().isoformat()})"
            for f in facts
        )
        return "\n".join(lines), False
