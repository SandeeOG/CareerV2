# Detective Monkey v2 — full build (P0 → P6)

This folder holds the code; the design documents live in
`Archtecture(notClaudeGen)/`. The codebase implements **P0–P6** and is a
**runnable, end-to-end application**:

- **P0/P1** — framework-independent **domain model** (`domain/`).
- **P2** — the **intelligence engines** (`engines/`, `contracts/`).
- **P3** — the **data layer**: expanded value objects/events, repository **ports**
  + in-memory **adapters** (`application/ports.py`, `infrastructure/`).
- **P4** — the **backend**: clean/hexagonal application services, providers,
  event bus, and an optional REST adapter (`application/`, `interfaces/`).
- **P5** — the **frontend**: a token-driven, accessible SPA served by the API
  (`interfaces/rest/static/`) covering the full journey.
- **P6** — **production**: Dockerfile + compose, health checks, GitHub Actions
  CI, stateless/config-external runtime.

The core (domain + engines + application + in-memory infrastructure) still has
**zero runtime dependencies**; databases, AI providers and FastAPI are optional
adapters that plug in behind ports — the domain never depends on them.

## What is (and isn't) here

Per the architecture (`P0/00_ARCHITECTURE_PRINCIPLES.md`) and the build order in
`map.txt`, Phases P0/P1 produce **only intelligence/domain** — *no database, no
API, no frontend, no AI provider, no engine algorithms*. Those arrive in later
phases and **depend on** this layer; this layer never depends on them.

Accordingly, `src/detective_monkey/` contains:

- **Pure domain objects** — entities, value objects, enums, relationships.
- **Invariants** — enforced in `__post_init__` (immutability, evidence/version
  requirements, range checks).
- **Engine contracts** — `Protocol` interfaces only; implementations are Phase 2.

There are **zero runtime dependencies** (stdlib `dataclasses` only). This is the
strongest reading of the principles: framework independence (§13), provider
independence (§11), determinism and testability without external services (§24).
Pydantic / ORM / FastAPI may wrap these objects at the boundaries in later phases.

## Layout → source document

| Package | Implements | Doc |
|---|---|---|
| `domain/common` | ids, versioning, provenance, confidence, scores, evidence, events | cross-cutting (00, 10, 18) |
| `domain/knowledge_graph` | nodes, edges, ontology | `P1/17` |
| `domain/skills` | `Skill`, `StudentSkill`, `CareerSkill`, `SkillGap`, relationships | `P1/13` |
| `domain/career` | `Career` graph + layers + similarity + progression | `P1/12` |
| `domain/education` | pathways, qualifications, institutions, competencies, gaps | `P1/14` |
| `domain/labour_market` | snapshots, demand/supply, salary, AI impact, scores | `P1/15` |
| `domain/student` | `Student`, timeline, scores, reliability, **SIP** | `P1/11` |
| `domain/recommendation` | `Recommendation`, dimensions, weights, evidence, **request/response contracts** | `P1/16`, `P2/25 §19` |
| `domain/explanation` | `Explanation` (AI-layer boundary object) | `P1/10 §12` |
| `domain/memory` | episodic / procedural / longitudinal memory | `P1/19` |
| `contracts` | `Engine` protocol, `EngineResult`, `IntelligenceContext`, layers | `P1/18` |

## Dependency rule

A module may import only from `common` and from modules **below** it in the
layering (`domain/__init__.py` documents the order). Reverse dependencies are
prohibited (`10 §16`, `18 §19`). The canonical semantic layer
(`knowledge_graph`) sits at the bottom; `recommendation` sits near the top and
consumes `skills` + `education`.

## Key invariants encoded

- **Immutability** of the SIP, `Recommendation`, `Evidence`, `Career`, KG
  nodes/edges, `LabourMarketSnapshot`, and memory records (`frozen=True`).
- **Evidence required**: `DerivedFeature`, a known `StudentSkill`, and every
  `Recommendation` must carry evidence.
- **Versioning everywhere**: every entity carries a `Version`; derived objects
  pin their input versions via `VersionSet` for reproducibility.
- **No fabricated data**: unknown quantities are `None`, never a defaulted `0`
  (`11 §13 INV-08`).
- **Deterministic boundary**: `IntelligenceLayer.is_deterministic` marks
  Evidence→Decision; Explanation/Interaction may use AI (`18 §16`).

## P2 — Intelligence engines

The engines live in `src/detective_monkey/engines/`. Every engine implements the
uniform contract from `contracts/` (doc 20): one `EngineRequest` in, one
`EngineResponse` out, through a fixed lifecycle (validate → run → metrics →
build response). Failures are structured `EngineError`s — successful execution
never relies on exceptions. Engines own no persistence/API/UI; tunable logic
(assessment definitions, feature formulas, aggregation rules, weights, prompts)
is supplied as data or injected strategies, never hardcoded.

| Engine | Layer | Doc | Notes |
|---|---|---|---|
| `contracts` (base + registry) | — | 20 | `BaseEngine`, `EngineRequest/Response`, errors, health, `EngineRegistry` |
| `assessment` | evidence | 21 | responses → validated **evidence** (reverse scoring, quality, timing) |
| `evidence` | evidence | 22 | observations → canonical **Evidence Graph** (normalize, dedupe, conflicts) |
| `feature_engineering` | inference | 24 | evidence → **features** via external formulas + topological deps |
| `student_intelligence` | inference | 23 | features → immutable **SIP** (construct/domain reasoning, reliability) |
| `recommendation` | decision | 25 | orchestrates pluggable **matchers** → ranked recommendations |
| `explanation` | explanation | 26 | **Decision Graph** + Explanation Object; optional LLM port |
| `retrieval` | knowledge | 27 | retrieval-first context assembly; graph before vector |
| `agent` | interaction | 28 | conversational **orchestrator**; computes nothing itself |
| `evaluation` | inference | 29 | read-only quality metrics across every layer |

**The deterministic boundary** (18 §16) is encoded in `IntelligenceLayer.is_deterministic`:
evidence → decision are deterministic and reproducible; explanation and
interaction may use a provider-agnostic LLM. The AI engines run fully without an
LLM (deterministic templates), and any LLM output is faithfulness-checked.

The full chain runs end-to-end:

```
assessment → evidence → feature_engineering → student_intelligence
          → recommendation → explanation → evaluation
```

`tests/test_engine_pipeline.py` exercises exactly this chain and asserts the
documented invariants (evidence-backed recommendations, skill-gap detection,
deterministic outputs, evaluation coverage).

## P3 / P4 — data + backend

Clean Architecture with strict inward dependencies (`400` §9): **API →
Application → Domain → Infrastructure**. The domain never imports a framework.

| Layer | Package | Responsibility |
|---|---|---|
| Ports | `application/ports.py` | Repository / event-publisher / provider interfaces (`404`, `405`, `409`) |
| Application | `application/services.py` | Use-cases orchestrating engines + repos + events (`403`); DTOs + `ServiceResult` envelope |
| Composition | `application/container.py` | `Backend` — wires engines + in-memory infra in one line |
| Infrastructure | `infrastructure/` | In-memory repositories, event bus (idempotency + DLQ), providers (template LLM, vector index), platform services (clock, ids, config) |
| Interface | `interfaces/rest/` | Optional FastAPI adapter + pure response envelope (`401`) |

The five use-cases — `SubmitAssessment`, `GenerateProfile`,
`GenerateRecommendations`, `ExplainRecommendation`, `AskAgent` — run the P2
engines, persist aggregates through repository ports, and publish domain events
after commit. `tests/test_backend_pipeline.py` drives the whole chain end-to-end
on in-memory infrastructure.

**Swapping in real infrastructure** (PostgreSQL, Neo4j, Anthropic, Qdrant) is a
pure adapter change in `infrastructure/` + the composition root — no domain,
engine or application code changes (`30` INV-08, `409` INV-01).

## Run the app

```bash
cd v2
python -m pip install -e ".[api]"            # FastAPI + uvicorn
uvicorn detective_monkey.interfaces.rest.asgi:app --reload   # or: detective-monkey
# open http://localhost:8000
```

Or with Docker:

```bash
cd v2
docker compose up --build      # http://localhost:8000
```

The server ships a seeded demo (assessment, careers, knowledge), so the full
journey works immediately: **enter your name → take the assessment → see your
evidence-based profile → get explainable recommendations → chat with the AI
coach.** The SPA is served at `/`; the REST API lives under `/api/v1`
(`/api/v1/health` for liveness).

## Develop / test

```bash
cd v2
python -m pip install -e ".[dev,api]"
python -m pytest                    # domain + engine + backend + HTTP-journey tests
```

The tests double as executable documentation of the domain invariants — each
cites the design document it protects.

See `ADR/0001-domain-foundation.md` for the rationale behind these choices.
