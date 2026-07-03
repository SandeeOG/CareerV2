# The Detective Monkey Engineering Bible

> **Status:** Living document · **Covers:** v2 codebase as of 2026-07-02 (commit lineage `c4a1c70 → dbfde9b` + Knowledge Platform)
> **Audience:** senior engineers, AI researchers, system architects, future maintainers
> **Mandate:** this is not documentation of what exists — it is a *design review that documents*. Every chapter (a) explains the system as built, precisely enough to rebuild it, and (b) critically evaluates it, compares alternatives, and records the recommended target design.

---

## How to read this document

The Bible is organized as nine chapters. Each chapter explains its subject from
the **three synchronized perspectives** (Conceptual / Engineering / Research)
and across the **five abstraction levels** (Vision → Product → System →
Component → Algorithm). To avoid a combinatorial explosion of headings, the
perspectives are woven into the prose and each chapter closes with a
**Design Review** section — the internal-review verdict: what is right, what is
wrong, what a superior design looks like, and why.

A reader who wants only the critical evaluation can read
[Chapter 8](08-design-review.md) — the consolidated review and target
architecture — and follow its cross-references backward.

A reader who wants to rebuild the platform reads chapters 1–7 in order; every
mechanism is explained down to the algorithm, with pseudo-code where the source
is non-obvious and direct file references (`src/detective_monkey/...`)
everywhere else. Nothing is treated as a black box: where the current
implementation is a placeholder-grade heuristic, the chapter says so explicitly
and explains both the heuristic *and* the algorithm that should replace it.

## Chapter map

| # | Chapter | Contents |
|---|---------|----------|
| 1 | [Vision & Constitution](01-vision-and-constitution.md) | Executive summary · product vision · the Software Constitution (the invariants that govern all code) · core design principles · product philosophy · user journey |
| 2 | [Complete System Walkthrough](02-system-walkthrough.md) | The complete life of one request, from browser open to analytics, every transformation and object named · sequence diagrams · the six-layer intelligence architecture |
| 3 | [Domain Model](03-domain-model.md) | Every value object and aggregate: identifiers, versioning, provenance, confidence, scores, events, Career, Student, Knowledge Graph primitives · lifecycle, ownership, validation, persistence for each |
| 4 | [The Engine Layer](04-engine-layer.md) | The universal engine contract · Assessment, Evidence, Feature Engineering, Student Intelligence, Intelligence Engine v1 (five-stage pipeline, all algorithms), Ranker, Mentor, Recommendation, Explanation, Retrieval, Agent, Evaluation · psychometric and ranking theory |
| 5 | [The Knowledge Platform](05-knowledge-platform.md) | Acquisition pipeline · normalization & entity resolution · validation & conflict resolution · graph construction & traversal · generation (heuristic + LLM) · retrieval pipeline · dynamic knowledge, caching, regional/salary/labour intelligence · provenance & versioning |
| 6 | [Application, API & Frontend](06-application-api-frontend.md) | Composition root · application services & DTOs · REST envelope and every endpoint's request lifecycle · the SPA · authentication & authorization (current absence, required design) |
| 7 | [Operations](07-operations.md) | Deployment, Docker, CI/CD · observability (logging, metrics, analytics) · performance & scalability model · security & privacy · disaster recovery · testing strategy |
| 8 | [The Consolidated Design Review](08-design-review.md) | Ranked findings (P0–P3) · superior architectures with rationale, alternatives and trade-offs · the target architecture · migration plan that preserves the constitution |
| 9 | [Research Foundations & Roadmap](09-research-and-roadmap.md) | Psychometrics (CTT/IRT), RIASEC & O*NET, recommender-systems theory, KG embeddings, IR, XAI, decision theory, calibration · future AI integrations · technical-debt register · ten-year evolution |

## Reading conventions

- **`path/to/file.py`** — a claim grounded in that source file. If the Bible and
  the code disagree, the code wins and the Bible must be amended (see
  Constitution, Art. X).
- **INV-xx** — an invariant from the architecture documents cited in module
  docstrings (e.g. `20_ENGINE_CONTRACTS.md §7`). The design documents live
  outside this repo (`Archtecture(notClaudeGen)/`); where the Bible restates an
  invariant it restates it fully, so the Bible is self-sufficient.
- **⚠ Review** — inline critical finding; the full analysis lives in the
  chapter's Design Review section and is indexed in Chapter 8.
- Diagrams are Mermaid; render on GitHub or any Mermaid-capable viewer.

## One-paragraph summary of the system

Detective Monkey v2 is a **career-intelligence platform for students**: a
zero-dependency Python core implementing a strict hexagonal architecture — an
immutable, versioned **domain model**; a fleet of deterministic **engines**
behind a single request/response contract layered as
Evidence → Knowledge → Inference → Decision → Explanation → Interaction; an
**application layer** of one-use-case services composed in a single container;
a self-generating **Knowledge Platform** (sources → normalize → validate →
graph) that is the sole source of career truth; optional adapters for FastAPI
(REST + SPA) and LLM providers (Gemini today) that degrade gracefully to
deterministic behaviour; and in-memory infrastructure adapters that stand in
for the future Postgres/Neo4j/Redis/vector deployment. The product promise is
**explainable guidance, not prediction**: every recommendation carries scores,
confidence, evidence and provenance, and the LLM is never allowed to invent a
fact — it reasons over retrieved knowledge or it says nothing.
