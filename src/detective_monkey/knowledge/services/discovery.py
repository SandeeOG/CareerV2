"""CareerDiscoveryService — natural-language exploration over the graph.

"Careers using mathematics", "careers for introverts", "remote careers",
"careers without programming": the Discovery Engine extracts facets from the
question deterministically, filters and traverses the Knowledge Graph, and the
LLM (when present) only *explains* the retrieved result. Related, alternative,
hidden and emerging careers and career families all come from relationship
traversal — none of them are curated lists.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.knowledge_graph.node import Node
from ...domain.knowledge_graph.ontology import NodeType, RelationshipType
from ..generators.llm import LLMPort
from ..graph.traversal import GraphTraversal
from ..models.dynamic import DynamicFactType
from ..normalizers.text import tokens
from ..prompts.templates import answer_prompt
from ..sources.dynamic import DynamicKnowledgeProvider


@dataclass(frozen=True, slots=True)
class DiscoveryFacet:
    """One extracted constraint: match these themes, or exclude them."""

    name: str
    keywords: frozenset[str]
    exclude: bool = False


# Deterministic facet rules. A facet matches a career through its semantic
# tags, description and metadata — themes generated at ingest time, not
# manually curated per query.
_FACETS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    # facet name, query triggers, career-side keywords
    ("mathematics", ("mathematics", "math", "maths"), ("mathematics", "math",
                                                       "statistics", "quantitative")),
    ("remote", ("remote", "work from home"), ("remote",)),
    ("high_salary", ("high salary", "well paid", "high paying", "highest paying"),
     ("high-salary", "high salary", "lucrative")),
    ("creative", ("creative", "creativity", "artistic"), ("creative", "design",
                                                          "art")),
    ("low_stress", ("low stress", "relaxed", "calm"), ("low-stress", "low stress")),
    ("introvert", ("introvert", "introverts", "quiet"), ("independent",
                                                         "analytical", "focused")),
    ("programming", ("programming", "coding", "code"), ("programming", "coding",
                                                        "software")),
    ("science", ("science", "scientific"), ("science", "research")),
    ("helping", ("helping people", "help people", "social impact"),
     ("healthcare", "teaching", "social")),
)

_NEGATIONS = ("without", "no ", "not involving", "avoid", "besides", "other than")


def extract_facets(query: str) -> tuple[DiscoveryFacet, ...]:
    q = query.lower()
    facets = []
    for name, triggers, career_keywords in _FACETS:
        matched = next((t for t in triggers if t in q), None)
        if matched is None:
            continue
        prefix = q[: q.index(matched)]
        exclude = any(neg in prefix[-20:] for neg in _NEGATIONS)
        facets.append(
            DiscoveryFacet(name, frozenset(career_keywords), exclude=exclude)
        )
    return tuple(facets)


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    query: str
    facets: tuple[DiscoveryFacet, ...]
    careers: tuple[Node, ...]
    rationale: str
    generated_by_llm: bool = False


class CareerDiscoveryService:
    """Retrieval-based career exploration. The graph retrieves; the LLM explains."""

    def __init__(
        self,
        traversal: GraphTraversal,
        dynamic_provider: DynamicKnowledgeProvider | None = None,
        llm: LLMPort | None = None,
    ) -> None:
        self._traversal = traversal
        self._dynamic = dynamic_provider
        self._llm = llm

    # -- natural-language exploration -----------------------------------------

    def discover(self, query: str, limit: int = 10) -> DiscoveryResult:
        facets = extract_facets(query)
        careers = self._career_nodes()

        if facets:
            careers = tuple(c for c in careers if self._matches(c, facets))
        else:
            # No facet — fall back to relevance search restricted to careers.
            careers = tuple(
                n for n in self._traversal.search(query, limit=limit * 2)
                if n.node_type is NodeType.CAREER
            )
        careers = tuple(sorted(careers, key=lambda n: n.canonical_name))[:limit]
        rationale, used_llm = self._explain(query, careers)
        return DiscoveryResult(query, facets, careers, rationale, used_llm)

    # -- relationship traversal -------------------------------------------------

    def related_careers(self, career_name: str, limit: int = 10) -> tuple[Node, ...]:
        return self._linked(
            career_name,
            frozenset({RelationshipType.RELATED_TO, RelationshipType.LEADS_TO}),
            limit,
        )

    def alternative_careers(self, career_name: str, limit: int = 10) -> tuple[Node, ...]:
        alternatives = self._linked(
            career_name, frozenset({RelationshipType.ALTERNATIVE_TO}), limit
        )
        if alternatives:
            return alternatives
        # Careers sharing this career's skills are its natural alternatives.
        career = self._traversal.find_by_name(career_name)
        if career is None:
            return ()
        skills = self._traversal.neighbours(
            career.id.value,
            node_types=frozenset({NodeType.SKILL}),
        )
        counts: dict[str, tuple[int, Node]] = {}
        for skill in skills:
            for other in self._traversal.neighbours(
                skill.id.value, node_types=frozenset({NodeType.CAREER})
            ):
                if other.id == career.id:
                    continue
                n, _ = counts.get(other.id.value, (0, other))
                counts[other.id.value] = (n + 1, other)
        ranked = sorted(
            counts.values(), key=lambda cn: (-cn[0], cn[1].canonical_name)
        )
        return tuple(node for _, node in ranked[:limit])

    def career_family(self, career_name: str, limit: int = 15) -> tuple[Node, ...]:
        """Careers in the same industry — two hops through BELONGS_TO."""
        career = self._traversal.find_by_name(career_name)
        if career is None:
            return ()
        industries = self._traversal.neighbours(
            career.id.value,
            node_types=frozenset({NodeType.INDUSTRY}),
            relationship_types=frozenset({RelationshipType.BELONGS_TO}),
        )
        family: dict[str, Node] = {}
        for industry in industries:
            for member in self._traversal.neighbours(
                industry.id.value, node_types=frozenset({NodeType.CAREER})
            ):
                if member.id != career.id:
                    family[member.id.value] = member
        return tuple(sorted(family.values(), key=lambda n: n.canonical_name))[:limit]

    def hidden_careers(self, interest: str, limit: int = 10) -> tuple[Node, ...]:
        """Careers two hops from an interest — reachable, but rarely surfaced."""
        seeds = self._traversal.search(interest, limit=3)
        if not seeds:
            return ()
        one_hop = self._traversal.expand(
            tuple(n.id.value for n in seeds), depth=1
        )
        two_hop = self._traversal.expand(
            tuple(n.id.value for n in seeds), depth=2
        )
        near = {n.id.value for n in one_hop.nodes} | {n.id.value for n in seeds}
        hidden = [
            n for n in two_hop.nodes
            if n.node_type is NodeType.CAREER and n.id.value not in near
        ]
        return tuple(sorted(hidden, key=lambda n: n.canonical_name))[:limit]

    def emerging_careers(self, limit: int = 10) -> tuple[Node, ...]:
        """Careers whose dynamic demand signal is rising, or tagged emerging."""
        careers = self._career_nodes()
        emerging = [c for c in careers if "emerging" in c.semantic_tags]
        if self._dynamic is not None:
            for career in careers:
                if career in emerging:
                    continue
                facts = self._dynamic.fetch_facts(
                    career.canonical_name, DynamicFactType.HIRING_TREND
                )
                if any("rising" in f.summary.lower() or "growing" in f.summary.lower()
                       for f in facts):
                    emerging.append(career)
        return tuple(sorted(emerging, key=lambda n: n.canonical_name))[:limit]

    # -- helpers -----------------------------------------------------------------

    def _career_nodes(self) -> tuple[Node, ...]:
        return self._traversal.nodes_of_type(NodeType.CAREER)

    def _matches(self, career: Node, facets: tuple[DiscoveryFacet, ...]) -> bool:
        text = " ".join(
            (
                career.canonical_name,
                career.description,
                *career.semantic_tags,
                *(v for _, v in career.metadata.items),
            )
        )
        career_tokens = tokens(text)
        for facet in facets:
            hit = any(
                tokens(keyword) <= career_tokens or keyword in text.lower()
                for keyword in facet.keywords
            )
            if facet.exclude and hit:
                return False
            if not facet.exclude and not hit:
                return False
        return True

    def _linked(
        self,
        career_name: str,
        relationship_types: frozenset[RelationshipType],
        limit: int,
    ) -> tuple[Node, ...]:
        career = self._traversal.find_by_name(career_name)
        if career is None:
            return ()
        linked = self._traversal.neighbours(
            career.id.value,
            node_types=frozenset({NodeType.CAREER}),
            relationship_types=relationship_types,
        )
        return linked[:limit]

    def _explain(self, query: str, careers: tuple[Node, ...]) -> tuple[str, bool]:
        if not careers:
            return ("No careers in the knowledge base match those constraints yet; "
                    "the base grows with every generation run.", False)
        if self._llm is not None:
            generated = self._llm.generate(answer_prompt(query, careers, ())).strip()
            if generated:
                return generated, True
        names = ", ".join(c.canonical_name for c in careers)
        return (f"Retrieved from the knowledge graph for '{query}': {names}.", False)
