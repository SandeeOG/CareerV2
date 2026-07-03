# Chapter 4 — The Engine Layer

Engines are the processing components of the platform. This chapter explains
the universal contract, then every engine — purpose, inputs/outputs,
algorithms with complexity, failure behaviour, extension points — and closes
with the design review, including the chapter's most important architectural
finding (E-1: the duplicated reasoning stack).

## 4.1 The universal engine contract (`contracts/engine.py`)

**Why one contract.** Heterogeneous component interfaces are where large
systems rot: each pairwise integration invents its own error handling,
versioning and observability. Detective Monkey has exactly one:

```
EngineRequest[PayloadT]{context, payload, configuration, metadata}
        │ execute() = validate → _run → wrap
        ▼
EngineResponse[ResultT]{status, engine_version, result, confidence,
                        provenance, events, warnings, errors, metrics, metadata}
```

Mechanics worth restating precisely:

- `execute()` **never raises.** Validation errors, `EngineException`s and
  unexpected exceptions all become structured `EngineResponse(FAILED)` with
  typed `EngineError`s; `RETRYABLE_ERRORS` (timeout/unavailable/dependency)
  tells *orchestration* what may be retried — retry logic never lives inside
  an engine.
- `EngineOutcome` is a mutable accumulator *inside* `_run` only; the response
  is frozen. This keeps engine bodies readable without leaking mutability.
- Every response self-reports `execution_ms` plus engine-specific metrics as
  strings in `Attributes` — observability by construction.
- `EngineMetadata` declares name, implementation version, layer (Chapter 2
  §2.1), determinism flag, and the shared `CONTRACT_VERSION` — implementations
  version independently of the contract.
- `HealthReport` gives orchestrators a uniform liveness probe.

**Alternatives considered (review).** (a) Free-form service classes — rejected:
loses uniform observability and the no-raise guarantee. (b) A message-bus
actor model — rejected at this scale: the engines are synchronous, pure and
fast; a bus adds latency and failure modes without concurrency wins.
(c) The chosen contract's cost is ceremony for trivial engines — accepted; the
ceremony *is* the audit trail. Verdict: keep, unchanged.

## 4.2 Assessment Engine (EVIDENCE)

**Purpose.** Measurement, not interpretation: transforms structured responses
into validated, standardized `Evidence` (INV-06: it never produces profiles or
recommendations).

**Validation** (all structured errors): definition id+version match; unknown
question ids; duplicate responses; scale-range violations; missing-policy
enforcement (REJECT requires full completion).

**Scoring algorithm** (O(n) in responses): reverse-scored flip
`v' = max + min − v`; linear normalization to 0–100:
`(v − min)/(max − min) × 100`; per-construct arithmetic mean.
**Quality metrics:** completion ratio; speeding flag per item
(duration < 800 ms); consistency across item pairs. Evidence ids derive
deterministically from inputs → identical submissions are idempotent.
**Confidence per evidence:** blends quality factors as named
`ConfidenceFactor`s.

**Research view.** This is Classical Test Theory (sum/mean scoring of Likert
items with reverse-keying — Likert 1932) with response-time screening (Wise &
Kong 2005, effort-moderated scoring). Two items per construct is far below
reliability norms (Cronbach's α needs ≥ 3–4 items to be meaningful).
⚠ **E-4:** the *architecture* is right (instrument as versioned data;
per-construct evidence), the *instrument* is a demo. Replacement path: a
30–60-item bank with IRT calibration (graded response model), adaptive
selection (maximum information criterion), and person-fit statistics — all of
which slot behind the existing `AssessmentDefinition`/`AssessmentResult`
contract without touching any downstream code. Chapter 9 §9.1.

## 4.3 Evidence & Feature Engineering & Student Intelligence (EVIDENCE→INFERENCE)

- **Evidence Engine** builds the per-student **EvidenceGraph** from validated
  evidence — the append-only observation store the SIP pipeline reads.
- **Feature Engineering Engine** computes versioned `DerivedFeature`s from
  evidence via declared formulas (`evidence_mean`, …) defined as data
  (`FeatureDefinition`); no feature exists without a definition and evidence
  references.
- **Student Intelligence Engine** aggregates features into the raw SIP under a
  versioned `ReasoningConfig` (construct sources, weighted aggregation rules) —
  again configuration, not code.

These three form the P2 "measurement pipeline". **⚠ E-1 preview:** the live
API path (`intelligence_service`) bypasses them, going Assessment →
Intelligence-v1 directly; the two pipelines overlap in responsibility. See
§4.8.

## 4.4 Intelligence Engine v1 — the single reasoning component (INFERENCE)

Five deterministic stages (fully traced in Chapter 2 §2.3 step 3; algorithms
in `signals.py`, `reasoner.py`, `confidence.py`, `builder.py`). Contractual
properties that matter architecturally:

- **Stages are injectable `Protocol`s** (`SignalExtractor`, `TraitReasoner`):
  an LLM-based extractor or Bayesian reasoner replaces a stage without
  touching the engine — the designed upgrade path for real ML.
- **Every number is explainable**: thresholds are named constants; every trait
  carries evidence; the profile carries computed confidence and metadata.
- **Complexity:** O(signals + areas) — microseconds; reasoning is never the
  bottleneck.

**Research view.** The signal→trait mapping is an expert-system prior: five
interest areas as fixed linear combinations of signals is a hand-rolled,
5-dimensional cousin of RIASEC (Holland 1959). The honest description: a
*calibratable placeholder* whose contract anticipates its replacement.
Superior algorithm (Chapter 9 §9.2): learn the mapping — factor analysis over
item banks for construct validity, then a hierarchical Bayesian model
(partial pooling across students) that produces posterior distributions rather
than point estimates; `Confidence` then becomes posterior variance instead of
a weighted blend. The current confidence formula
(0.4·completeness + 0.3·decisiveness + 0.3·evidence-count) is a reasonable
*proxy* but conflates "answered a lot" with "measured well".

## 4.5 Ranking (`ranker.py`) and the P2 Recommendation Engine (DECISION)

**Ranker (live path).** Weighted linear combination of five [0,1] dimension
scores (weights in `RankingWeights`, no magic numbers), labour-market as a
bounded additive bonus (INV-08: adjusts, never dominates), deterministic
tiebreak, rich explainable output. Personality matching is the strongest
dimension: distance-based fit to each requirement's optimal `ScoreRange`
weighted by importance — a genuine, defensible algorithm.

**Weaknesses (findings):**
- **E-2 — skill matching is a gate, not a match.** All career skills match if
  `skill_vector["technical"] ≥ 0.5`, else all miss. Superior: per-skill
  matching via the Knowledge Graph — career REQUIRES skill edges vs student
  skill vector components mapped through the same canonical skill nodes;
  cosine or coverage-weighted Jaccard; complexity O(career skills). The graph
  and vectors already exist; this is a wiring gap. **P1.**
- **E-3 — dead dimensions dilute.** Learning-style and constraints return
  constants (0.6, 1.0) but carry 20% of core weight, compressing real score
  spread. Either implement (constraints: filter/penalty from
  `CareerConstraints` vs career metadata; style: career→style affinity table
  on the Career aggregate) or zero their weights until implemented. **P1,
  one-line mitigation.**
- **E-5 — keyword→interest-area mapping** (`_AREA_KEYWORDS` over career names)
  is brittle ("Data Product Manager" → Programming? Business?). Superior:
  tag careers with interest areas *in the Knowledge Graph at generation time*
  (the platform already writes semantic tags), making the mapping data.
  **P2.**

**P2 Recommendation Engine (parallel path).** A more complete decision
orchestrator: pluggable match engines, score+confidence aggregation, MMR
diversity re-ranking (λ=0.7 — relevance vs diversity, Carbonell & Goldstein
1998), warnings with severities, immutable `Recommendation` aggregates pinning
`VersionSet`s, events. It is architecturally *superior* to the ranker but is
not on the live API path.

## 4.6 Explanation, Retrieval, Agent (EXPLANATION/INTERACTION)

- **Explanation Engine**: builds a **decision graph** from a recommendation's
  dimension scores/evidence, then renders a deterministic `PromptPackage`
  (system prompt + sections + question, versioned template). LLM optional;
  template fallback produces the same grounded content (Art. IX).
- **Knowledge Retrieval Engine**: graph-first retrieval with source-priority
  ordering (decision > knowledge > evidence > memory > vector), token-overlap
  relevance, dedupe, budget, and a versioned prompt whose system message
  forbids contradicting the graphs. INV: vector search supplements, never
  overrides; the LLM never retrieves.
- **Career Intelligence Agent**: "think with the platform, speak with the
  LLM." Intent classification (ordered keyword rules) → capability dispatch →
  engine orchestration → grounded response; missing prerequisites produce a
  clarifying question, not speculation. Determinism flag in its metadata
  reflects whether an LLM is attached.
- **Mentor** (`mentor.py`): 422 lines of deterministic derivations powering
  every premium surface (readiness, opportunity, action, roadmap, skill gap,
  comparison, coach framing). It is EXPLANATION-layer logic implemented as
  pure functions over (profile, matches, insights) — trivially testable, and
  the reason the product works with zero LLM.

**AI-component checklist** (required by the mandate, for the LLM-touching
components): system prompts are code-reviewed constants; prompt construction
is deterministic assembly of retrieved sections; context = graphs → memory →
vector; confidence comes from retrieval coverage, never model self-report;
hallucination prevention = retrieval-first + explicit prohibition + validation
gates (knowledge side) + template fallback; output validation = shape checks
(description length/JSON schema) on the knowledge side, none needed on the
explanation side (LLM output is presented as narration, clearly derived);
fallback = deterministic templates everywhere.

## 4.7 Token-overlap relevance — the shared retrieval primitive

Both retrieval engines and the knowledge search rank by
`|Q ∩ T| / |Q|` (or Jaccard variants) over lowercased alphanumeric tokens,
with stopword filtering on the engine side. Properties: zero dependencies,
fully deterministic, explainable ("matched tokens: …"), O(tokens); weaknesses:
no synonymy ("ML" ≠ "machine learning"), no morphology, English-biased.
**Superior design** (staged, Chapter 8): (1) alias/synonym expansion at query
time using the graph's own alias tables — no new deps, big recall win;
(2) BM25 over node text — still dependency-free, principled term weighting;
(3) embedding ANN as a *supplement* behind the existing `VectorIndex` port
(the port and hash-embedding stub already exist), preserving INV "vector never
overrides canonical". This ordering buys most of the recall for a fraction of
the operational cost of jumping straight to vectors.

## 4.8 Design Review — the engine layer

**E-1 (the chapter's headline): two parallel reasoning stacks.**
Path A (P2): Assessment → Evidence → Features → SIP → RecommendationEngine
(matchers, MMR, immutable aggregates, weight configs). Path B (live):
Assessment → Intelligence-v1 → ranker → mentor. Both score career fit with
different algorithms, weights and output types; the API uses B while A holds
the better decision-layer machinery (diversity, persisted immutable
recommendations, version pinning) and the better measurement machinery
(evidence graph, versioned features). Risks: divergent scores for the same
student, double maintenance, and constitutional ambiguity about "the single
reasoning component".

**Resolution (recommended, with rationale).** Converge on **one pipeline**
keeping each side's best parts: Assessment → Evidence Graph → Features →
Intelligence-v1 stages (as the interpretation layer, consuming features
instead of raw evidence — its stage-injection design makes this a payload
change) → RecommendationEngine as the *only* decision layer, with the current
ranker refactored into a `MatchEngine` plugin (its personality matcher is the
best matcher in the codebase) and mentor consuming the persisted
`Recommendation` aggregates. Alternatives: (a) delete Path A — rejected,
loses diversity/persistence/version-pinning that the product needs anyway;
(b) keep both and document — rejected, divergence is a correctness bug waiting
for a user. Cost: a focused refactor behind stable contracts; the tests for
both paths already exist. **P1.**

| ID | Finding | Recommendation |
|----|---------|----------------|
| E-1 | Duplicated reasoning stack (above) | Converge; ranker becomes a MatchEngine. **P1** |
| E-2 | Skill match is a single-signal gate | Graph-based per-skill matching. **P1** |
| E-3 | Neutral dimensions carry 20% weight | Implement constraints/style or zero weights. **P1** |
| E-4 | 12-item CTT instrument beneath production claims | IRT item bank + adaptive testing behind the same contract. **P1 (product), P2 (eng)** |
| E-5 | Career-name keyword interest mapping | Move to graph tags at generation time. **P2** |
| E-6 | Confidence formulas are heuristic blends | Bayesian posterior variance once E-4 lands; until then, document formulas as calibration targets and log calibration data (Ch. 9 §9.5). **P2** |
| E-7 | Ranker recomputed per request (W-1) | Cache per (profile version, catalog version). **P2** |
