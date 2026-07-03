# Chapter 7 — Operations

## 7.1 Deployment & CI/CD (as built)

- **Image:** `python:3.12-slim`, installs `.[api]`, stateless, env-configured
  (`DM_HOST/DM_PORT`, optional `GEMINI_API_KEY/GEMINI_MODEL`), container
  HEALTHCHECK hits `/api/v1/health`; uvicorn entrypoint. **Compose** runs the
  single service; the file's comments correctly note Postgres/Neo4j/Redis
  arrive as adapter swaps with no app changes.
- **CI** (`.github/workflows/ci.yml`): on push/PR — install with dev+api
  extras, run the full pytest suite, build the Docker image. Fast (<2 min)
  because the core is dependency-free.

**Review.** The stateless-image discipline is right. Gaps: no image push /
registry / deploy stage (CI stops at build); no vulnerability scanning; no
multi-stage build (dev headers ship in the runtime image); no non-root user.
All are small, standard hardening steps. **P2.**

## 7.2 The state problem (O-1 — the operational headline)

Everything is in-memory: students, profiles, recommendations, memories, the
Knowledge Graph, caches, mentor memory. A restart is total amnesia; two
replicas are two disjoint universes. This is *by design* for the demo and the
ports make the fix an adapter project, but it dominates every other
operational concern and gates real users.

**Target persistence (recommended):**
- **Postgres** for aggregates (students, SIPs, recommendations, memories,
  events): append-only tables mirroring the append-only repos; optimistic
  concurrency via the existing `Version`; JSONB for `Attributes`.
- **Same Postgres for the graph initially** (nodes/edges tables + adjacency
  indexes) — the traversal depth is 1–2 and volumes are modest; move to
  **Neo4j** only when multi-hop discovery queries dominate (K-1's second
  stage). Rationale: one datastore to operate beats two half-operated ones.
- **Redis** for `KnowledgeCache` (TTLs map 1:1) once >1 replica exists.
- **Outbox pattern** for events: write events in the aggregate transaction,
  publish from the outbox — the current bus publishes after save with no
  atomicity (acceptable in-memory, wrong with a real DB). **P1 with DB.**

## 7.3 Observability (current: engine metrics only)

Engines self-report `execution_ms` + metrics per response, and the bus counts
published/delivered/dead-lettered — good bones, no export. **Target (staged):**
1. **Structured logs** (stdlib `logging` + JSON formatter, correlation id from
   `IntelligenceContext` on every line) — no new deps. **P1.**
2. **Metrics endpoint**: map engine metrics + bus metrics + cache stats to
   Prometheus text format (~80 lines, no client lib needed). **P1.**
3. **Tracing** (OTel, adapter-layer only) when >1 service exists. **P3.**
4. **Analytics**: an event-bus subscriber persisting `DomainEvent`s to an
   events table = the analytics feed and the future learning-loop input
   (O-3); today the stream exists and nothing listens. **P1.**

## 7.4 Background execution (O-2)

Knowledge generation/enrichment are background-shaped callables with no
scheduler. Target: a worker process running `platform.generate()` /
`enrich_missing()` on cron-like schedule with `GenerationReport`s persisted
and alerting on rejection spikes; queue (Redis/RQ or APScheduler in-process
first) chosen at the same time as Redis. Generation must never block a
request path (constitutional: Performance section of the platform spec). **P1.**

## 7.5 Security & privacy

Current surface: no auth (W-4), no TLS termination in-repo (deploy concern),
LLM key via env (correct), no PII encryption, no retention policy, one XSS
risk (A-5). The **privacy architecture** (with C-1/D-6): classify all
student-derived data as sensitive; per-student erasure = delete rows + tombstone
events (the append-only design makes this a deliberate, auditable operation);
export as a first-class use case; data minimization already helps (the system
stores evidence and scores, not raw conversations — keep it that way: the
`ConversationContext` is consumed, not persisted). Threat model headline:
the LLM boundary — prompt-injection via student text into prompts is
mitigated by prompts treating retrieved content as data + output shape
checks, but add explicit injection tests. **P1.**

## 7.6 Performance & scalability model

Current: single process; every request CPU-bound over in-memory data;
`rank_careers` O(careers · dims) per read (W-1/E-7); graph ops O(V/E) scans
(K-1); LLM calls synchronous with 20 s timeout (the only real latency).
Scale path in order: (1) cache ranked matches; (2) index the graph repo;
(3) externalize state (§7.2) → horizontally stateless API; (4) async LLM
calls with request-level timeout budget; (5) background generation (§7.4).
No microservices: the module boundaries (engines, knowledge, application) are
the future service seams *if ever needed*, but nothing at 10⁵ users requires
them if state is external.

## 7.7 Disaster recovery & testing

**DR:** with §7.2, DR = Postgres PITR + image redeploy; the Knowledge Graph is
*regenerable from sources* — a unique property: the KG's DR story is "re-run
generation", so back up sources + reports, not just the graph.
**Testing (current):** 82 tests — invariants, value objects, engine
behaviours, knowledge platform end-to-end (26), API via FastAPI TestClient;
deterministic core makes the suite fast and flake-free. **Gaps:** no property-
based tests (Hypothesis is ideal for scoring/normalization invariants), no
calibration/eval harness for reasoning quality (Ch. 9 §9.5), no load tests,
no injection tests (§7.5). **P2.**

## 7.8 Design Review — operations

| ID | Finding | Recommendation |
|----|---------|----------------|
| O-1 | Total in-memory state | §7.2 persistence plan; outbox for events. **P0 (for real users)** |
| O-2 | No scheduler/worker for generation | §7.4. **P1** |
| O-3 | Events published, never consumed | Analytics subscriber → events table. **P1** |
| O-4 | No structured logging/metrics export | §7.3 stages 1–2. **P1** |
| O-5 | CI lacks push/scan/non-root/multi-stage | Standard hardening. **P2** |
| O-6 | No eval/calibration harness in CI | Ch. 9 §9.5; gate reasoning changes on eval deltas. **P2** |
