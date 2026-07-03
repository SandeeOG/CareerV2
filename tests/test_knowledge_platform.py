"""Tests for the Knowledge Generation Platform.

Each test protects one of the platform's guiding principles: generate/
normalize/validate/store, layered knowledge, retrieval-first reasoning, and
"the LLM never invents factual career data".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from detective_monkey.application.container import Backend
from detective_monkey.domain.common.attributes import Attributes
from detective_monkey.domain.common.confidence import Confidence
from detective_monkey.domain.common.events import EventName
from detective_monkey.domain.common.provenance import Provenance, SourceType
from detective_monkey.domain.common.scores import UnitInterval
from detective_monkey.domain.knowledge_graph.ontology import (
    NodeType,
    RelationshipType,
)
from detective_monkey.infrastructure.event_bus import InMemoryEventBus
from detective_monkey.infrastructure.repositories import (
    InMemoryKnowledgeGraphRepository,
)
from detective_monkey.knowledge import KnowledgePlatform
from detective_monkey.knowledge.cache import KnowledgeCache
from detective_monkey.knowledge.generators.llm import extract_json_array
from detective_monkey.knowledge.models import (
    CandidateRelationship,
    DynamicFact,
    DynamicFactType,
    RawKnowledgeRecord,
    RawRelationshipHint,
    SourceMetadata,
)
from detective_monkey.knowledge.retrieval import KnowledgeIntent, classify
from detective_monkey.knowledge.services.discovery import extract_facets
from detective_monkey.knowledge.sources import (
    InMemoryDatasetSource,
    StaticDynamicKnowledgeProvider,
)
from detective_monkey.knowledge.validators import Severity

# ---------------------------------------------------------------------------
# Test doubles + seed data
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 2, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


class FakeLLM:
    """Deterministic LLM double: answers by prompt shape, counts calls."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt) -> str:
        self.calls.append(prompt.user_question)
        if prompt.user_question.startswith("Describe"):
            return (
                "A field that studies the collection and interpretation of "
                "numerical information across the sciences."
            )
        if prompt.user_question.startswith("Which known concepts"):
            # One valid proposal, one invented entity, one bogus type.
            return (
                'Sure! [{"relationship": "RELATED_TO", "target": "Data Scientist"},'
                ' {"relationship": "USES", "target": "Unicorn Wrangler"},'
                ' {"relationship": "EATS", "target": "Data Scientist"}]'
            )
        return f"Grounded answer about: {prompt.user_question}"


def _meta(source_id: str, reliability: float = 0.9) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        name=source_id,
        source_type=SourceType.GOVERNMENT_STATISTICS,
        reliability=UnitInterval(reliability),
    )


def _requires(target: str) -> RawRelationshipHint:
    return RawRelationshipHint(
        RelationshipType.REQUIRES, target, NodeType.SKILL, UnitInterval(0.9)
    )


def _seed_records() -> tuple[RawKnowledgeRecord, ...]:
    return (
        # Three raw names that must collapse into one "Software Engineer".
        RawKnowledgeRecord(
            "src_a", NodeType.CAREER, "Software Developer",
            description="Designs and builds software systems.",
            tags=("software", "technology"),
            attributes=Attributes.of(industry="Technology"),
            relationships=(_requires("Python"), _requires("Algorithms")),
        ),
        RawKnowledgeRecord("src_a", NodeType.CAREER, "Programmer"),
        RawKnowledgeRecord("src_a", NodeType.CAREER, "Backend Engineer"),
        RawKnowledgeRecord(
            "src_a", NodeType.CAREER, "Data Scientist",
            description="Analyzes data using statistics and machine learning.",
            tags=("analytical", "statistics", "technology", "remote"),
            attributes=Attributes.of(industry="Technology"),
            relationships=(
                _requires("Python"),
                _requires("Statistics"),
                _requires("Algorithms"),
            ),
        ),
        RawKnowledgeRecord(
            "src_a", NodeType.SKILL, "Python",
            description="A general-purpose language.",
            attributes=Attributes.of(difficulty="beginner"),
        ),
        RawKnowledgeRecord(
            "src_a", NodeType.SKILL, "Statistics",
            description="Mathematics of data.",
            attributes=Attributes.of(difficulty="intermediate"),
        ),
        RawKnowledgeRecord(
            "src_a", NodeType.SKILL, "Algorithms",
            description="Problem-solving procedures.",
            attributes=Attributes.of(difficulty="advanced"),
        ),
        RawKnowledgeRecord(
            "src_a", NodeType.INDUSTRY, "Technology",
            description="The technology industry.",
        ),
        RawKnowledgeRecord(
            "src_a", NodeType.COUNTRY, "Germany", description="A country in Europe."
        ),
        RawKnowledgeRecord(
            "src_a", NodeType.REGION, "Assam", description="A state in India."
        ),
    )


def _platform(llm=None, clock=None, publisher=None) -> KnowledgePlatform:
    platform = KnowledgePlatform(
        InMemoryKnowledgeGraphRepository(),
        clock=clock,
        llm=llm,
        publisher=publisher,
    )
    platform.sources.register(InMemoryDatasetSource(_meta("src_a"), _seed_records()))
    # A second source corroborating one career under a different alias.
    platform.sources.register(
        InMemoryDatasetSource(
            _meta("src_b", reliability=0.7),
            (
                RawKnowledgeRecord(
                    "src_b", NodeType.CAREER, "Software Developer",
                    description="Builds applications.",
                ),
            ),
        )
    )
    return platform


def _salary_provider() -> StaticDynamicKnowledgeProvider:
    provider = StaticDynamicKnowledgeProvider(_meta("salary_api"))
    provider.add(
        DynamicFact(
            subject="Data Scientist",
            fact_type=DynamicFactType.SALARY,
            summary="Median salary EUR 65,000 per year.",
            region="Germany",
            provenance=Provenance(SourceType.JOB_BOARD, "salary api"),
        )
    )
    provider.add(
        DynamicFact(
            subject="Data Scientist",
            fact_type=DynamicFactType.REGIONAL_DEMAND,
            summary="Strong demand in Bengaluru and Hyderabad; relocation typical.",
            region="Assam",
            provenance=Provenance(SourceType.GOVERNMENT_STATISTICS, "labour stats"),
        )
    )
    return provider


# ---------------------------------------------------------------------------
# Normalization + generation
# ---------------------------------------------------------------------------


def test_generation_merges_synonyms_into_one_canonical_career() -> None:
    platform = _platform()
    report = platform.generate()

    assert report.records_fetched == len(_seed_records()) + 1
    engineer = platform.traversal.find_by_name("Software Engineer")
    assert engineer is not None
    # All raw names survive as aliases of the canonical entity.
    assert {"Software Developer", "Programmer", "Backend Engineer"} <= set(
        engineer.aliases
    )
    # No separate node exists for the synonyms.
    careers = platform.traversal.nodes_of_type(NodeType.CAREER)
    assert sorted(c.canonical_name for c in careers) == [
        "Data Scientist", "Software Engineer",
    ]


def test_corroboration_raises_confidence() -> None:
    platform = _platform()
    platform.generate()
    engineer = platform.traversal.find_by_name("Software Engineer")
    lonely = platform.traversal.find_by_name("Assam")
    assert engineer.quality_score.value > lonely.quality_score.value


def test_generation_is_idempotent_and_versions_grow() -> None:
    platform = _platform()
    platform.generate()
    first_nodes = platform.graph.list_nodes()
    first_edges = platform.graph.list_edges()

    platform.generate()  # regeneration run
    assert len(platform.graph.list_nodes()) == len(first_nodes)
    assert len(platform.graph.list_edges()) == len(first_edges)
    engineer = platform.traversal.find_by_name("Software Engineer")
    assert engineer.version.number == 2  # updated, not duplicated


def test_generation_derives_relationships_and_publishes_events() -> None:
    bus = InMemoryEventBus()
    imported: list[str] = []
    bus.subscribe(EventName.KNOWLEDGE_LINKED, "t", lambda e: imported.append(e.aggregate_id))
    platform = _platform(publisher=bus)
    report = platform.generate()

    assert report.edges_written > 0
    assert imported  # KNOWLEDGE_LINKED events reached the bus
    # Careers sharing skills became RELATED_TO without any manual curation.
    edge_types = {e.edge_type for e in platform.graph.list_edges()}
    assert RelationshipType.REQUIRES in edge_types
    assert RelationshipType.RELATED_TO in edge_types
    assert RelationshipType.BELONGS_TO in edge_types  # industry mapping


def test_relationship_hints_resolve_through_aliases() -> None:
    platform = _platform()
    platform.generate()
    engineer = platform.traversal.find_by_name("Software Engineer")
    skills = platform.traversal.neighbours(
        engineer.id.value, node_types=frozenset({NodeType.SKILL})
    )
    # Hints were declared on "Software Developer" but land on the canonical node.
    assert {s.canonical_name for s in skills} == {"Python", "Algorithms"}


def test_learning_path_orders_skills_by_difficulty() -> None:
    platform = _platform()
    platform.generate()
    path = platform.generation.learning_path_for("Data Scientist")
    assert [n.canonical_name for n in path] == ["Python", "Statistics", "Algorithms"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validation_rejects_relationship_to_unknown_entity() -> None:
    platform = _platform()
    platform.sources.register(
        InMemoryDatasetSource(
            _meta("src_bad"),
            (
                RawKnowledgeRecord(
                    "src_bad", NodeType.CAREER, "Quant Analyst",
                    description="Financial modelling.",
                    relationships=(
                        RawRelationshipHint(
                            RelationshipType.REQUIRES, "Nonexistent Skill",
                            NodeType.SKILL,
                        ),
                    ),
                ),
            ),
        )
    )
    report = platform.generate()
    assert report.relationships_rejected >= 1
    codes = {i.code for i in report.issues if i.severity is Severity.ERROR}
    assert "unknown_endpoint" in codes


def test_validation_flags_cross_source_conflicts_as_warnings() -> None:
    platform = KnowledgePlatform(InMemoryKnowledgeGraphRepository())
    for source_id, hours in (("s1", "40"), ("s2", "60")):
        platform.sources.register(
            InMemoryDatasetSource(
                _meta(source_id),
                (
                    RawKnowledgeRecord(
                        source_id, NodeType.CAREER, "Pilot",
                        description="Flies aircraft.",
                        attributes=Attributes.of(weekly_hours=hours),
                    ),
                ),
            )
        )
    report = platform.generate()
    conflict = [i for i in report.issues if i.code == "conflicting_attribute"]
    assert conflict and conflict[0].severity is Severity.WARNING
    assert report.entities_accepted == 1  # kept, flagged — not rejected


def test_low_confidence_knowledge_never_enters_the_graph() -> None:
    platform = KnowledgePlatform(InMemoryKnowledgeGraphRepository())
    platform.sources.register(
        InMemoryDatasetSource(
            _meta("rumours", reliability=0.1),
            (RawKnowledgeRecord("rumours", NodeType.CAREER, "Dragon Trainer"),),
        )
    )
    report = platform.generate()
    assert report.entities_rejected == 1
    assert platform.traversal.find_by_name("Dragon Trainer") is None


# ---------------------------------------------------------------------------
# Cache + dynamic (Layer 2) knowledge
# ---------------------------------------------------------------------------


def test_cache_expires_entries_by_ttl() -> None:
    clock = FakeClock()
    cache = KnowledgeCache(clock, default_ttl_seconds=100)
    cache.put("a:1", "value")
    assert cache.get("a:1") == "value"
    clock.advance(101)
    assert cache.get("a:1") is None


def test_cache_invalidate_by_prefix_and_stats() -> None:
    cache = KnowledgeCache()
    cache.put("regional:x", 1)
    cache.put("regional:y", 2)
    cache.put("decision:z", 3)
    assert cache.invalidate("regional:") == 2
    assert cache.get("decision:z") == 3
    stats = cache.stats()
    assert stats.hits == 1 and stats.entries == 1


def test_dynamic_facts_are_cached_not_refetched() -> None:
    calls = []

    class CountingProvider:
        def metadata(self):
            return _meta("counting")

        def fetch_facts(self, subject, fact_type, region=""):
            calls.append((subject, fact_type, region))
            return _salary_provider().fetch_facts(subject, fact_type, region)

    platform = _platform()
    platform.generate()
    platform.register_dynamic_provider(CountingProvider())

    query = "what is the salary of a data scientist in Germany"
    first = platform.ask(query)
    fetches_after_first = len(calls)
    second = platform.ask(query)

    assert first.facts and second.facts
    assert len(calls) == fetches_after_first  # second answer came from cache


# ---------------------------------------------------------------------------
# Retrieval pipeline
# ---------------------------------------------------------------------------


def test_intent_classification() -> None:
    assert classify("compare data science vs software engineering") is KnowledgeIntent.COMPARISON
    assert classify("what is the salary of a pilot") is KnowledgeIntent.FACT
    assert classify("how do I become a data scientist") is KnowledgeIntent.LEARNING_PATH
    assert classify("show me careers using mathematics") is KnowledgeIntent.DISCOVERY


def test_pipeline_answers_without_llm_from_retrieved_knowledge_only() -> None:
    platform = _platform()
    platform.generate()
    platform.register_dynamic_provider(_salary_provider())

    answer = platform.ask("what is the salary of a data scientist in Germany")
    assert not answer.generated_by_llm
    assert answer.region == "Germany"
    assert any(f.fact_type is DynamicFactType.SALARY for f in answer.facts)
    assert "65,000" in answer.answer  # retrieved fact, not invented
    assert answer.provenance is not None and answer.provenance.references


def test_pipeline_reports_unknown_instead_of_inventing() -> None:
    platform = KnowledgePlatform(InMemoryKnowledgeGraphRepository())
    answer = platform.ask("salary of an astronaut on Mars")
    assert answer.nodes == () and answer.facts == ()
    assert "No canonical knowledge" in answer.answer


def test_pipeline_uses_llm_for_reasoning_over_retrieved_context() -> None:
    llm = FakeLLM()
    platform = _platform(llm=llm)
    platform.generate()
    answer = platform.ask("tell me about data scientist careers")
    assert answer.generated_by_llm
    assert answer.answer.startswith("Grounded answer about:")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discovery_facet_extraction_supports_negation() -> None:
    facets = extract_facets("creative careers without programming")
    by_name = {f.name: f for f in facets}
    assert not by_name["creative"].exclude
    assert by_name["programming"].exclude


def test_discovery_filters_careers_by_facets() -> None:
    platform = _platform()
    platform.generate()

    result = platform.discovery.discover("careers using mathematics")
    assert [c.canonical_name for c in result.careers] == ["Data Scientist"]

    result = platform.discovery.discover("careers without programming")
    names = [c.canonical_name for c in result.careers]
    assert "Software Engineer" not in names
    assert "Data Scientist" in names

    result = platform.discovery.discover("remote careers")
    assert [c.canonical_name for c in result.careers] == ["Data Scientist"]


def test_discovery_related_and_family_come_from_the_graph() -> None:
    platform = _platform()
    platform.generate()

    related = platform.discovery.related_careers("Data Scientist")
    assert [n.canonical_name for n in related] == ["Software Engineer"]

    family = platform.discovery.career_family("Data Scientist")
    assert [n.canonical_name for n in family] == ["Software Engineer"]

    alternatives = platform.discovery.alternative_careers("Data Scientist")
    assert [n.canonical_name for n in alternatives] == ["Software Engineer"]


# ---------------------------------------------------------------------------
# Decision support + regional intelligence
# ---------------------------------------------------------------------------


def test_decision_compare_reports_facts_and_unknowns() -> None:
    platform = _platform()
    platform.generate()
    platform.register_dynamic_provider(_salary_provider())

    report = platform.decisions.compare(
        ("Data Scientist", "Software Engineer"),
        criteria=(DynamicFactType.SALARY,),
        region="Germany",
        student_context="I love statistics and analytical work",
    )
    ds_cell = report.cell("Data Scientist", DynamicFactType.SALARY)
    se_cell = report.cell("Software Engineer", DynamicFactType.SALARY)
    assert ds_cell.known and not se_cell.known
    assert "no current data" in report.summary  # unknown stays unknown
    assert "Closest match to your stated context: Data Scientist" in report.summary


def test_decision_requires_two_options() -> None:
    platform = _platform()
    with pytest.raises(ValueError):
        platform.decisions.compare(("Only One",))


def test_regional_advice_is_generated_and_cached() -> None:
    clock = FakeClock()
    platform = _platform(clock=clock)
    platform.generate()
    platform.register_dynamic_provider(_salary_provider())

    advice = platform.regional.advise("Data Scientist", "Assam")
    assert "Bengaluru" in advice.advice  # retrieved regional fact
    assert advice.facts

    again = platform.regional.advise("Data Scientist", "Assam")
    assert again is advice  # served from cache, not regenerated


# ---------------------------------------------------------------------------
# LLM generation stays validated
# ---------------------------------------------------------------------------


def test_extract_json_array_parses_prose_wrapped_json() -> None:
    assert extract_json_array('noise [1, 2, [3]] trailing') == [1, 2, [3]]
    assert extract_json_array("no json here") is None
    assert extract_json_array("[broken") is None


def test_enrichment_fills_descriptions_and_validates_llm_relationships() -> None:
    llm = FakeLLM()
    platform = _platform(llm=llm)
    # Add an isolated, description-less concept for enrichment to work on.
    platform.sources.register(
        InMemoryDatasetSource(
            _meta("src_sparse"),
            (RawKnowledgeRecord("src_sparse", NodeType.KNOWLEDGE_AREA, "Numerology"),),
        )
    )
    platform.generate()
    report = platform.generation.enrich_missing()

    node = platform.traversal.find_by_name("Numerology")
    assert report.descriptions_enriched >= 1
    assert node.description  # filled by the (validated) LLM proposal
    assert node.provenance.source is SourceType.DERIVED

    # The LLM proposed three relationships; only the one linking two *known*
    # entities with a whitelisted type survived validation.
    edges = platform.graph.edges_of(node.id.value)
    assert len(edges) == 1
    assert edges[0].edge_type is RelationshipType.RELATED_TO


def test_llm_never_generates_during_plain_retrieval() -> None:
    llm = FakeLLM()
    platform = _platform(llm=llm)
    platform.generate()
    llm.calls.clear()
    platform.traversal.search("data scientist")
    platform.discovery.related_careers("Data Scientist")
    assert llm.calls == []  # retrieval itself never consulted the model


# ---------------------------------------------------------------------------
# Container integration
# ---------------------------------------------------------------------------


def test_backend_composes_the_knowledge_platform() -> None:
    backend = Backend(use_llm=False)
    platform = backend.knowledge_platform
    assert platform.graph is backend.knowledge_graph

    platform.sources.register(InMemoryDatasetSource(_meta("src_a"), _seed_records()))
    report = platform.generate()
    assert report.entities_accepted > 0
    # Knowledge written through the platform is visible to the shared repo.
    assert backend.knowledge_graph.list_nodes()
