# ADR 0001 — P0/P1 Domain Foundation in Pure Python

> Status: Accepted · Date: 2026-06-30
>
> Required by 00_ARCHITECTURE_PRINCIPLES.md §26 (Architectural Decision Records).

## Problem

Phases P0 (Foundation) and P1 (Domain) must be implemented as code that later
phases build upon. We needed to decide *what* to build, in what language/shape,
and where it lives — without violating the principle that the domain precedes
(and is independent of) database, API, AI, and UI.

## Options considered

1. **Treat P0/P1 as documents only** — write no code. Rejected: the user asked
   to "code the v2 foundation," and the domain is the highest-leverage thing to
   make concrete early.
2. **Build domain objects with Pydantic / SQLModel** — convenient validation and
   future ORM/serialization. Rejected for the *domain* layer: it couples the
   model to a third-party library and a serialization concern, contradicting
   framework independence (§13) and provider independence (§11).
3. **Pure stdlib `dataclasses`, zero runtime dependencies** — chosen.

## Decision

- Implement the P1 domain model as **immutable `@dataclass(frozen=True, slots=True)`
  value objects/entities** in `src/detective_monkey/domain/`, with **zero runtime
  dependencies**.
- Implement P1/18 as **`Protocol` contracts only** in `src/detective_monkey/contracts/`.
  No engine algorithms (those are Phase 2).
- Enforce documented invariants in `__post_init__` (ranges, evidence
  requirements, version pinning, no self-loops, owner requirements).
- Represent unknown values as `None`, never a defaulted `0` (11 §13 INV-08).
- Enforce a strict module layering with the Knowledge Graph at the bottom; a
  module imports only from `common` and lower layers.
- Live in a new project under `v2/` (`pyproject.toml`, `src/`, `tests/`),
  separate from the v1 `detective-monkey` repo.

## Consequences

**Positive**

- The domain is reproducible, deterministic, and testable with no external
  services — exactly what §24 demands of the intelligence engines.
- Later phases can wrap these objects: Pydantic at the API boundary (P5), an ORM
  / graph store at the data boundary (P4), AI providers at the explanation
  boundary (P3) — none of which require changing the domain.
- Invariants are executable and self-documenting (the test suite cites the
  document each invariant protects).

**Negative / trade-offs**

- No automatic JSON (de)serialization or schema generation in the domain layer;
  adapters must provide it later. Accepted — it keeps the core pure.
- Hand-written validation instead of a validation library. Accepted — the rules
  are few and explicit.

## Scope notes

- Engine *implementations*, scoring math, candidate generation, traversal
  algorithms, persistence, and prompts are intentionally **out of scope** for
  P0/P1 and are deferred to P2+.
- If a contradiction is found *within* P0/P1 while later phases are built, the
  resolution is a documented change to the spec + a new ADR — not silent drift
  in code (00 §1).
