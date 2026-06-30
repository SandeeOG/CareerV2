# Intelligence Engine v1

The single reasoning component of Detective Monkey. It sits between the
Assessment Engine and recommendation ranking:

```
Assessment → Intelligence Engine → rank_careers → Recommendations → Explanation
```

Recommendation no longer interprets anything: it receives a
`StudentIntelligenceProfile` and scores careers.

## Public API

Exactly one public method:

```python
IntelligenceEngine().build(
    assessment,            # AssessmentResult (from the Assessment Engine)
    student,               # domain Student
    conversation=None,     # optional ConversationContext
    preferences=None,      # optional StudentPreferences
) -> StudentIntelligenceProfile
```

Career scoring lives in `rank_careers(profile, careers, weights, labour_bonus)`.

## Pipeline (deterministic, no LLM)

| Stage | File | Output |
|---|---|---|
| 1. Signal Extraction | `signals.py` | `StudentSignals` (11 normalized 0-1 signals) |
| 2. Trait Inference | `reasoner.py` | strengths, weaknesses, interests, personality, learning style, work env, skill/career vectors |
| 3. Evidence Collection | `reasoner.py` | every trait carries `EvidenceItem`s |
| 4. Profile Construction | `builder.py` | immutable `StudentIntelligenceProfile` |
| 5. Confidence Estimation | `confidence.py` | overall `confidence` 0-1 |

## `StudentIntelligenceProfile`

Immutable. Fields: `strengths`, `weaknesses`, `interests`, `personality`,
`learning_style`, `preferred_work_environment`, `career_constraints`,
`skill_vector`, `career_vector`, `evidence`, `confidence`, `metadata`.

> Note: this is distinct from `domain.student.profile.StudentIntelligenceProfile`
> (the low-level construct/domain-score SIP). This object is the *interpreted*,
> recommendation-facing profile. The low-level SIP remains available for the P2
> deterministic engine path.

## Ranking

`ranker.py` scores each career with weighted dimensions — all weights in
`RankingWeights` (no magic numbers):

```
score = skill_match + interest_match + personality_match
      + learning_style_match + career_constraints (+ labour_market_bonus)
```

Each `CareerRecommendation` exposes: `score`, `confidence`, `reasons`,
`top_strengths`, `top_interests`, `matching_skills`, `evidence`,
`missing_information`, `dimension_scores`.

## Extension points (not implemented)

Injected as Protocols so future work plugs in without contract changes:

- `SignalExtractor` — LLM/embedding-based signal extraction.
- `TraitReasoner` — knowledge-graph / Bayesian inference.
- `ScoringStrategy` — learning-to-rank / embedding similarity scoring.

```python
IntelligenceEngine(signal_extractor=my_llm_extractor, trait_reasoner=my_kg_reasoner)
```
