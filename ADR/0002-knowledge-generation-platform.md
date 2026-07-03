# ADR 0002 — Knowledge Generation Platform

> Status: Accepted · Date: 2026-07-02
>
> Required by 00_ARCHITECTURE_PRINCIPLES.md §26 (Architectural Decision Records).

## Problem

Detective Monkey must not become a manually maintained career database: no
hand-created careers, no hand-created relationships, no hardcoded per-country
records. It needs a platform that continuously generates, normalizes,
validates, enriches and updates its own Career Knowledge Base — the single
source of truth behind recommendations, discovery, the AI mentor, decision
intelligence and roadmaps.

## Options considered

1. **Curated seed data + admin tooling** — rejected: linear manual cost per
   career/country; contradicts the "generate, don't create" objective.
2. **LLM-generated knowledge written directly to storage** — rejected: the
   platform's grounding principle is that unvalidated model output never
   becomes truth; hallucinated salaries/universities would poison every
   downstream feature.
3. **A generation pipeline (sources → normalize → validate → graph) with
   layered knowledge and retrieval-first serving** — chosen.

## Decision

- New package `src/detective_monkey/knowledge/` with the sub-modules
  `models/ sources/ normalizers/ validators/ generators/ prompts/ graph/
  cache/ retrieval/ services/`, keeping the platform's zero-dependency rule
  (ADR 0001): stdlib only, frozen dataclasses, `Protocol`/ABC ports.
- **Three knowledge layers.** Core knowledge (careers, skills, relationships)
  is validated and stored permanently in the existing canonical Knowledge
  Graph (`domain/knowledge_graph`). Dynamic knowledge (salary, demand, visas)
  is retrieved through `DynamicKnowledgeProvider` ports and cached with TTLs —
  never persisted. Personalized intelligence is generated per request and
  never stored as truth.
- **One source contract.** Every dataset/API implements `KnowledgeSource`
  (`fetch/normalize/validate/metadata`); O*NET and ESCO adapters are presets
  of a generic delimited-file source. Sources are registered, replaceable and
  carry a reliability score used in validation and conflict resolution.
- **Deterministic identity.** Canonicalization (alias table + conservative
  fuzzy matching) merges duplicate concepts; node ids derive from entity
  slugs and edge ids from (type, source, target), making generation runs
  idempotent upserts rather than appends.
- **Validation is the write gate.** Imported, heuristic and LLM-generated
  knowledge all pass the same `ValidationPipeline` (missing fields, schema,
  confidence threshold, duplicates, cross-source conflicts, relationship
  endpoint checks) before touching the graph.
- **LLM at generation time only, and always constrained.** The
  `StructuredGenerator` may expand descriptions and propose relationships
  *between entities that already exist*; output is schema-parsed, filtered
  and re-validated. Retrieval and discovery never call the LLM to obtain
  facts; the retrieval pipeline uses it only to narrate retrieved context,
  with a deterministic fallback when no provider is configured.
- **Integration.** The platform reuses the existing
  `KnowledgeGraphRepository` port (extended additively with
  `get_node/list_edges/edges_of`), publishes `KNOWLEDGE_IMPORTED`/
  `KNOWLEDGE_LINKED` domain events on the existing bus, and is composed in
  the `Backend` container as `knowledge_platform`.

## Consequences

- Adding a country, industry or career means registering a source or
  provider, not writing records.
- Graph databases, vector search and embeddings can replace the in-memory
  adapters behind existing ports without refactoring.
- Generation runs are background-job-shaped (pure callables returning
  reports); scheduling/queueing infrastructure can adopt them as-is.
