# Chapter 9 — Research Foundations & Roadmap

The research view for the whole platform: the academic ground each subsystem
stands on, the algorithms that should succeed the current heuristics, and the
ten-year evolution — plus the technical-debt register in one place.

## 9.1 Psychometrics

**Current:** Classical Test Theory — Likert items, reverse-keying, mean
scoring, completion/speeding quality flags (Likert 1932; Wise & Kong 2005 on
response-time effort screening). **Successor:** Item Response Theory — a
graded response model (Samejima 1969) over a 30–60-item calibrated bank gives
item-level difficulty/discrimination, person-fit statistics, and *standard
errors per construct* (the missing ingredient for honest confidence);
adaptive testing (van der Linden & Glas 2010) then halves item count at equal
precision by maximum-information selection. Construct validity for interest
areas should anchor to **RIASEC** (Holland 1959) and O*NET's interest
profiler mappings rather than the bespoke five areas — this also makes
career-side interest tags free, since O*NET publishes RIASEC codes per
occupation (E-5's principled fix). Fairness: differential item functioning
(DIF) analysis per demographic once data exists (Art. XII).

## 9.2 Reasoning & confidence

**Current:** expert-system linear maps signal→trait, heuristic confidence
blends. **Successor:** hierarchical Bayesian trait models — partial pooling
across the student population (Gelman & Hill 2007) yields posteriors whose
variance *is* `Confidence` (E-6), and whose shrinkage handles sparse
first-session data gracefully. The stage-injection `Protocol`s in
`IntelligenceEngine` are the designed insertion point. LLM-based signal
extraction from conversation (replacing keyword boosts) belongs behind
`SignalExtractor` with the same validation-gate philosophy as knowledge
generation: extracted signals carry provenance `DERIVED` + confidence
discounts until corroborated by assessment.

## 9.3 Recommendation & ranking theory

**Current:** weighted linear scoring + MMR diversity (Carbonell & Goldstein
1998) in the P2 engine. **Successors, in adoption order:** (1) constraint
satisfaction as filtering (hard constraints prune, soft constraints penalize
— the `CareerConstraints` object anticipates this); (2) learning-to-rank
(LambdaMART-family) once the analytics sink (O-3) accumulates
acceptance/rejection labels — pointwise first, pairwise when volume allows;
(3) exploration: recommendation of careers is a *bandit with delayed,
biased feedback* — an ε-greedy slate slot for "hidden careers" both serves
discovery and de-biases training data; (4) calibrated score presentation
(Platt scaling / isotonic regression against observed outcomes). Fairness
constraints (demographic-blind inputs; exposure parity across career
categories) belong in the ranking layer, not post-hoc.

## 9.4 Knowledge graph & IR research

Entity resolution: blocking (K-4) → supervised matching (Magellan, Konda et
al. 2016) → embedding ER (Ditto, Li et al. 2020). Graph completion: the
LLM-proposal-behind-validation pattern is a practical instance of KG
completion; the classical alternatives (TransE/ComplEx/RotatE embeddings for
link prediction) become viable once the graph has 10⁴+ edges and can serve as
*candidate generators feeding the same validation pipeline* — the
architecture already has the right gate. Retrieval: the ladder of Ch. 8 §8.3
maps to the literature as lexical (BM25, Robertson & Zaragoza 2009) → dense
(bi-encoders) → hybrid with reciprocal-rank fusion; GraphRAG-style expansion
(retrieve seeds, expand via typed edges, rank the subgraph) is exactly what
`KnowledgeRetrievalPipeline` already does — the research upgrade is *scoring*
the expansion (personalized PageRank from seed nodes) instead of flat BFS.

## 9.5 Evaluation — the missing discipline

The platform has correctness tests but no *quality* evaluation. Required
harness (gates M4+ changes in CI): (a) **retrieval**: judged query set →
recall@k / nDCG per ladder rung; (b) **recommendations**: offline replay
against accumulated accept/reject events (once O-3 lands) with
counterfactual-safe metrics; (c) **calibration**: reliability diagrams for
confidence vs observed correctness; (d) **LLM surfaces**: groundedness checks
— every factual span in a narration must be attributable to a retrieved
node/fact (the provenance references make this mechanically checkable);
(e) **generation**: precision of accepted entities/relationships sampled per
`GenerationReport`. Publishable side-effect: the groundedness checker over
provenance-carrying prompts is a genuinely reusable contribution.

## 9.6 The learning loop (future)

Events exist for acceptance/rejection/goal-setting; nothing learns from them
yet. Loop design: events table (O-3) → nightly jobs producing (1) ranking
training data, (2) calibration updates, (3) knowledge feedback (careers whose
detail pages under-convert get enrichment priority), (4) instrument feedback
(items whose answers never move recommendations are candidates for
retirement). Every learned artifact is versioned data (`WeightConfiguration`
already models this) so Art. II reproducibility survives learning.

## 9.7 Future AI integrations

- **Career Twin / Simulation:** simulate a student's trajectory under a
  chosen roadmap — a Markov model over the graph's progression edges with
  labour-market transition priors; LLM narrates simulated paths; all
  transition probabilities retrieved/validated, never invented.
- **Multi-provider LLM:** the `_PromptLike` structural contract already
  serves any vendor; add Anthropic/OpenAI adapters + a router (cost/latency/
  capability tiers) in `ProviderFactory` (A-review, Ch. 6 §6.1).
- **Embeddings:** behind the existing `VectorIndex`/embedding ports, as the
  final retrieval rung and for related-career similarity.
- **University/scholarship intelligence:** new `KnowledgeSource`s +
  UNIVERSITY/SCHOLARSHIP fact types — the extension points exist; no new
  architecture.

## 9.8 Technical-debt register (single source)

P0: W-4, C-1/D-6, O-1 · P1: E-1, W-2/A-2/M-3, E-2, E-3, K-1, K-2, K-3/O-2,
W-3/A-6, A-3, A-5, O-3, O-4, E-4 · P2: C-2, C-3, D-2, D-3, D-4, A-1, A-4,
E-5, E-6, E-7/W-1, K-4, K-5, K-6, K-7, K-8, O-5, O-6 · P3: C-4, D-1, D-5,
OTel. (Analyses live in the owning chapters; migration order in Ch. 8 §8.4.)

## 9.9 Ten-year posture

The bet to protect: **the domain model and the validation-gated knowledge
loop outlive every model generation.** LLMs will keep getting better at
generation, extraction and narration — each improvement slots behind an
existing port (`SignalExtractor`, `StructuredGenerator`, `LLMPort`,
`VectorIndex`) and faces the same gate: *validated or rejected, provenance or
nothing, unknown over invented.* If, in ten years, frontier models can
reliably reason over raw context, the deterministic boundary moves — by
constitutional amendment, with an eval harness proving the move — but the
evidence chain, the version pinning and the knowledge gate remain, because
they are what make the system *accountable*, and accountability, not
intelligence, is this product's scarce resource.
