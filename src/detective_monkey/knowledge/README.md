# Knowledge Generation Platform

Detective Monkey does **not** maintain a career database by hand. This package
continuously **generates, normalizes, validates, enriches and stores** the
Career Knowledge Base, and serves it back through a retrieval-first pipeline.
It is the single source of truth for career knowledge behind the
Recommendation Engine, Intelligence Engine, Career Discovery, AI Mentor,
Decision Intelligence, the Career Simulator and Roadmaps.

## Guiding principles

- Never manually create thousands of careers or millions of relationships.
- Never hardcode country-specific information.
- **Generate → Normalize → Validate → Store → Reuse.**
- The LLM generates (behind validation) and explains (over retrieved facts).
  It never invents salaries, universities, certifications, visa rules or
  labour statistics, and it is never the retrieval mechanism.
- Zero runtime dependencies (ADR 0001); every external capability is a port.

## The three knowledge layers (`models/layers.py`)

| Layer | Examples | Lifecycle |
|---|---|---|
| **Core** | careers, skills, competencies, relationships, learning paths | generated once, validated, stored permanently in the Knowledge Graph |
| **Dynamic** | salary, demand, hiring trends, visas, scholarships, universities | retrieved through `DynamicKnowledgeProvider` ports, cached with a TTL, refreshed on expiry — never stored as permanent truth |
| **Personalized** | fit explanations, comparisons, regional advice, roadmaps | generated per request from profile + core + dynamic knowledge; cached briefly, never persisted |

## Architecture

```
knowledge/
    models/       RawKnowledgeRecord, CanonicalEntity, CandidateRelationship,
                  DynamicFact, KnowledgeLayer
    sources/      KnowledgeSource interface + SourceRegistry;
                  InMemoryDatasetSource, DelimitedFileSource,
                  ONetOccupationSource, EscoOccupationSource;
                  DynamicKnowledgeProvider port (+ static & composite adapters)
    normalizers/  slug/token utilities, AliasTable, Canonicalizer, EntityMerger
    validators/   checks (missing fields, schema, confidence, source
                  reliability, duplicates, conflicts, invalid relationships)
                  + ValidationPipeline — only validated knowledge is stored
    generators/   deterministic heuristics (relationship derivation, related
                  careers, industry mapping, learning paths, summaries) and
                  StructuredGenerator (LLM, generation-time only, validated)
    prompts/      deterministic, versioned prompt templates (grounding rules)
    graph/        GraphAssembler (idempotent upserts into the canonical
                  Knowledge Graph) and GraphTraversal (search, BFS expansion,
                  paths) over domain/knowledge_graph Node/Edge
    cache/        KnowledgeCache — clock-injected TTL cache, namespaced keys
    retrieval/    intent detection + the pipeline:
                  question → intent → knowledge retrieval → graph expansion
                  → dynamic retrieval → LLM reasoning → answer
    services/     KnowledgeGenerationService, CareerDiscoveryService,
                  DecisionSupportService, RegionalIntelligenceService,
                  KnowledgePlatform (composition facade)
```

## The generation loop (`KnowledgeGenerationService`)

```
source.fetch() → source.normalize() → source.validate()
  → Canonicalizer + EntityMerger        (merge duplicates, build aliases)
  → generators                          (hints, shared-skill relations,
                                         industry mappings, optional LLM)
  → ValidationPipeline                  (rejects; reports issues)
  → GraphAssembler                      (idempotent node/edge upserts,
                                         domain events on the bus)
```

Node ids derive from entity slugs and edge ids from (type, source, target),
so re-running generation *updates* the graph instead of duplicating it.
`enrich_missing()` is the continuous-improvement pass: it fills sparse
descriptions and proposes relationships for lonely nodes (LLM proposals may
only link entities that already exist; everything is re-validated). Both runs
are designed to execute as background jobs, never on a request path.

## Retrieval (`KnowledgeRetrievalPipeline`)

Retrieval always precedes reasoning. Without an LLM the pipeline still
answers deterministically from retrieved knowledge — grounding is a property
of the pipeline, not the model. Regional questions ("careers in Germany")
resolve by *retrieving* dynamic facts for the region, never by materializing
Career × Country records.

## Using it

```python
from detective_monkey.application.container import Backend
backend = Backend()
platform = backend.knowledge_platform

platform.sources.register(my_source)              # any KnowledgeSource
platform.register_dynamic_provider(my_provider)   # any DynamicKnowledgeProvider
report = platform.generate()                      # background generation run

answer = platform.ask("What careers use mathematics?")
result = platform.discovery.discover("remote careers without programming")
report = platform.decisions.compare(("Data Scientist", "Software Engineer"),
                                    region="Germany")
advice = platform.regional.advise("Data Scientist", "Assam")
```

## Extension points (interfaces only — plug in without refactoring)

- **New sources** (government APIs, LinkedIn, Coursera, edX, universities,
  salary/job APIs): implement `KnowledgeSource` or `DynamicKnowledgeProvider`
  and register.
- **Graph databases (Neo4j)**: implement `KnowledgeGraphRepository`
  (application/ports.py) and pass it to `KnowledgePlatform`.
- **Vector/semantic search**: supplement `GraphTraversal.search` behind the
  same signature; the pipeline is unchanged. Embedding providers already have
  a port in `infrastructure/providers.py`.
- **Background jobs / async**: `generate()` and `enrich_missing()` are
  self-contained callables ready for any scheduler or queue.
