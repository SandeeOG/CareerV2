# Product Strategy Review — From Recommendation to Discovery

*A first-principles pressure test of the proposed pivot: "Detective Monkey
should not tell students who they are; it should help them discover who they
are." Written against the actual v2 codebase and the existing vision
(docs/bible/01-vision-and-constitution.md). No code was changed.*

---

## 1. Product Philosophy — is discovery the better problem?

**Short answer: yes — but not for the reason you gave, and with two of your
assumptions needing serious correction.**

### Why the direction is right

The strongest argument for the discovery framing is not epistemological, it's
**economic**: in your target market (India; the codebase speaks LPA, CBSE
boards, Guwahati, home-state notes), the cost of a wrong career belief is
enormous and front-loaded. Stream lock-in happens at grade 10–11. Families
then spend 2–4 years and lakhs of rupees on entrance-exam preparation for a
career the student has *never experienced for a single hour*. A product that
converts false certainty into tested belief **before** that capital is
committed has a value proposition no recommendation engine can match, because
a recommendation — however well-calibrated — is still an untested belief.

Second, the discovery framing solves the recommendation framing's fatal
epistemic problem, which your own architecture already documents: the current
system infers 22 features from **self-report about a self the student hasn't
met yet**. A 15-year-old answering "I enjoy figuring out how machines work"
is reporting an *identity aspiration*, not a *revealed preference*. The
Student Evidence Engine merges sources by confidence — but every v1 source
(assessment, goals, even academics) is correlated self-perception. The one
thing that would decorrelate the evidence — actual experience — is exactly
what the discovery loop generates. So discovery isn't just a nicer philosophy;
it is **the only way to get evidence the current engine can't already get**.

Third: recommendation is a commodity trajectory. Free LLM chat already gives
any student a plausible "what career fits me" answer. Assessment→report is a
crowded space (Mindler, iDreamCareer, Univariety in India; Xello, Naviance,
YouScience abroad). Nobody owns the loop of *hypothesis → cheap experiment →
reflection → recalibration* for teenagers. That is a defensible identity.

### Where your assumptions need challenging

**Assumption 1 — that this is a fork in the road.** It isn't. You framed
recommendation vs discovery as opposing philosophies. They are stages of one
pipeline: **a discovery loop without a recommendation engine has no hypothesis
generator.** A student can't "test whether medicine fits" until something
plausibly ranked medicine above 280 alternatives. The current
IntelligenceEngine + ranker + affinity map doesn't get discarded — it gets
*demoted* from oracle to hypothesis generator. That demotion is a UI and
framing change more than an engine change. Don't burn the engine to make the
point.

**Assumption 2 — that students will do the actions.** This is the load-bearing
assumption of the entire vision and it is unvalidated. Recommendation is
consumption (low friction, one sitting). Discovery is homework. The dropout
cliff between "read your matches" and "spend two hours building something" is
where this product will live or die — and no amount of AI recalibration
matters if the reflection queue is empty. The hard problem of this product is
not modelling; it is **motivation design** (streaks, school integration,
assignments, social proof). Budget accordingly: the winning team here looks
more like Duolingo's habit team than like a recsys team.

**Assumption 3 — that actions generate valid evidence.** A bad two-hour
experience of "coding" (poorly chosen tutorial, wrong difficulty, bad day)
generates *confident noise*. One trial of one activity is an n=1 experiment
with massive measurement error, and teenagers' enjoyment of an activity is
confounded by novelty, difficulty calibration, and who they did it with. The
product needs to treat experience evidence the way the codebase already treats
AI extraction — validated, confidence-weighted, never a single-sample
overwrite. (The architecture is unusually ready for this; see §2.) But the
*science* — which micro-experiences actually predict career fit — does not
exist yet, in your product or anywhere. You will be inventing it, and you
should say so honestly rather than implying the loop is self-evidently valid.

**Assumption 4 — implicit — that the user is the buyer.** In India especially,
the economic buyer is the parent or the school, and both are answer-seeking:
parents pay for certainty ("which stream?"), schools pay for reports and
counsellor dashboards. A product whose honest pitch is "we will *reduce* your
child's certainty and replace it with experiments" is pedagogically superior
and commercially harder. The framing that sells is not "we won't tell you the
answer" but "**an answer you've tested is worth ten answers you've been
told**" — confidence through evidence, not certainty through authority.

**Verdict:** the discovery loop is the stronger long-term vision — it creates
data no competitor has, it fixes the self-report trap, and it matches the real
economics of the decision. But it succeeds or fails on engagement mechanics
and evidence validity, not on model quality, and it must be built *on top of*
the recommendation engine, not instead of it.

---

## 2. Existing Architecture — audit against the discovery philosophy

The uncomfortable/comforting truth: **the architecture is more aligned with
the discovery vision than the product is.** The constitution ("evidence before
inference", provenance on every claim, confidence everywhere) was written for
this pivot without knowing it. The conflicts are almost all at the product
surface, not the foundation.

### Already supports the philosophy (keep, and lean harder on)

| Component | Why it suddenly matters more |
|---|---|
| `domain/common/evidence.py`, `provenance.py`, `confidence.py` | Every claim already carries source + confidence. "Experience evidence" is one new `SourceType`, not a redesign. |
| **Student Evidence Profile** (`engines/student_evidence/schema.py`) | Built as *the* single source of student truth with confidence-weighted multi-source merging (`_merge_feature_sets`). Adding an experience source re-normalizes automatically — the spec's "future evidence sources (projects, competitions, extracurriculars)" clause anticipated exactly this. |
| **Open-response extraction pipeline** (`extraction.py`) | A post-action reflection ("how did building that feel?") is structurally identical to an open assessment answer: `OpenResponse → extract_with_ai → validate → merge`. The reflection pipeline is already written; it's just only invoked at assessment time. |
| **Career Pulse** (`definitions.py`, `apply_pulse`) | Already implements recency-weighted recalibration (0.6 new / 0.4 old). It is the discovery loop at 6-month resolution. The loop just needs to tick per-action instead of per-calendar. |
| **Human validation** (`apply_validation`) | The first "student corrects the model" mechanism — the philosophical seed of "help them discover, don't tell them." |
| **Append-only, versioned profiles** (`InMemoryProfileRepository.list_versions`, `VersionSet`) | A discovery product's core asset is the *trajectory*, not the snapshot. Versioning was a correctness decision; it becomes the product. |
| `domain/memory` (episodic/longitudinal memory) | Built, barely used. Under discovery it is the student's experiment journal — arguably the core aggregate. |
| **Knowledge base action fields** (`portfolio_ideas`, `projects`, `internships`, `youtube`, `courses` per career) | The raw material for an action catalog already exists across ~280 careers. Nobody has to write "try building a line-following robot" — it's in the data. |
| `mentor.todays_action` (`DailyAction`) | A vestigial one-step discovery loop already shipped. It recommends an action but never *hears back*. Closing that ear is the MVP (§4). |
| **Evidence→career affinity + ranker bonus hook** (`affinity.py`, `rank_careers(labour_bonus=)`) | Cheap per-student re-ranking after every new evidence item — recalibration is O(one function call), already wired through `_rebuild_intelligence`. |
| **Hexagonal ports** (`application/ports.py`) | Durable persistence (non-negotiable for a longitudinal product) is a pure adapter swap, as designed. |
| **Event bus** (`EVIDENCE_COLLECTED` events) | The natural spine for "action completed → evidence extracted → profile rebuilt → matches moved" without coupling. |

### Conflicts with the philosophy (the product surface lies about the architecture)

1. **Match scores presented as conclusions.** The premium cards say "95%
   match" — a point estimate with the visual authority of a verdict. The
   ranker actually *knows better*: `CareerRecommendation` carries
   `confidence` and `missing_information`, and the profile carries
   per-feature confidence — but the UI buries them. A discovery product must
   lead with the two-axis truth: **fit estimate × evidence strength**. "95%
   fit, based almost entirely on what you told us about yourself" is a
   hypothesis; the current UI renders it as an answer.

2. **The completion funnel.** The Student Growth card celebrates **"100%
   complete."** That is the recommendation worldview in one number: profile
   done, journey over. Under discovery there is no 100% — the equivalent
   metric is *momentum* (experiments run this term, beliefs updated). The
   growth checklist is the single most philosophically wrong element in the
   current product.

3. **Evidence is closed-world and static.** All four v1 sources are captured
   in one sitting. Nothing in `EvidenceSubmission` can represent "did X,
   felt Y" — there is no action/outcome evidence type, no timestamped
   evidence stream, no notion that newer experiential evidence should
   outrank older self-report.

4. **In-memory persistence.** Tolerable for a one-shot funnel; fatal for a
   product whose entire value is longitudinal. A student who returns after
   their first experiment to find the model forgot them has experienced the
   opposite of the pitch. This is the most urgent *infrastructure* conflict
   (and, per the ports design, the cheapest to fix).

5. **The one-shot report.** A downloadable "AI Career Report" is the
   artifact of the old philosophy — a terminal deliverable. It doesn't need
   deleting (parents/schools want it) but it must become a *progress report
   of tested hypotheses*, not a verdict document.

### Decisions that suddenly become more valuable

- **"The LLM explains; it does not know"** — in a product for minors making
  life decisions through experiments, deterministic-and-auditable
  recalibration is a trust and safety differentiator, not just engineering
  hygiene.
- **Knowledge platform as generated graph** — the action catalog (v3) and
  experiment templates (v4) are new *views over the same graph*, consistent
  with the "every feature is a view over one graph" moat thesis.
- **`ProfileMetadata.assessment_completeness` / reliability scaffolding** —
  becomes the "evidence strength" axis of the hypothesis board.

### Components to rethink

- **Growth card** → from completeness % to discovery momentum.
- **Career Pulse** → from calendar-driven macro-survey to event-driven
  micro-pulse (3 questions after every completed action); the 6-month pulse
  remains as the fallback for dormant students.
- **`RecommendationsDTO` / premium card** → add `evidence_strength` and
  "what would change this score" (the ranker's `missing_information`
  already computes the raw material).
- **Dashboard hierarchy** → today it leads with who you are and what
  matches; it should lead with **"your next experiment"** and treat matches
  as the lab bench, not the trophy shelf.

---

## 3. Product Evolution — three coherent versions

The through-line: **v3 closes the loop, v4 makes the loop trustworthy, v5
makes the loop compound.** Each version has one job.

### v3 — "Close the loop" (Hypotheses & Experiments)

*Job: a student can test a career belief and watch the model update.*

- **Stays:** the entire engine stack (assessment → evidence profile →
  intelligence → ranking → explanation), knowledge platform, coach, Explore.
  The 44-question assessment remains the cold-start hypothesis generator —
  discovery needs priors.
- **Changes:**
  - Matches are reframed as **hypotheses** with two visible axes: *fit*
    (current score) and *evidence strength* (how much of that score rests on
    tested experience vs self-report — derivable from source provenance in
    the evidence profile).
  - Growth card becomes **momentum** (experiments completed, beliefs
    updated, hypotheses retired).
  - Career Pulse becomes per-action micro-reflection; the 6-month pulse is
    the dormant-user fallback.
- **Added:**
  - **Action cards**: per-hypothesis smallest-next-actions generated
    deterministically from the knowledge base's existing `portfolio_ideas` /
    `projects` / `youtube` / `courses` fields ("Test 'Robotics engineer'
    this week: build a line-follower — ~2 hrs").
  - **Reflection capture**: 3 structured sliders (enjoyment, energy,
    would-do-again) + one open paragraph, flowing through the *existing*
    extraction pipeline as a new `EXPERIENCE` evidence source with higher
    merge weight than self-report.
  - **Durable persistence** (SQLite adapters behind existing ports).
- **Removed:** the "100% complete" framing; the report as a verdict (rewrite
  copy to "current state of tested hypotheses").
- **Why:** this is the minimum product where the pitch is demonstrable in
  one demo: *do a thing → tell us how it felt → watch your matches move,
  with an explanation of why.*

### v4 — "Trust the loop" (the longitudinal student model)

*Job: the recalibration is credible enough that students, parents and
counsellors believe the movement.*

- **Stays:** the v3 loop, untouched at the surface.
- **Changes:**
  - Evidence gains **time-awareness**: experiential evidence outweighs
    self-report; old self-report decays; `domain/memory` becomes the
    student's experiment journal and the profile becomes a *view over the
    journal* (the append-only design finally pays off).
  - The coach evolves from Q&A to **experiment designer**: "you enjoyed
    building but not documenting — next, test whether *debugging* energizes
    you," including contradiction surfacing ("you said you love biology;
    your two biology experiments both scored low enjoyment — worth one more
    test?").
- **Added:**
  - **Verified evidence**: teacher/school confirmation of projects,
    competitions, club participation (the spec's anticipated ERP/LMS
    evidence sources) — the first evidence that isn't self-reported at all.
  - **Comparative experiments**: paired actions designed to discriminate
    between two live hypotheses (the `compare` surface becomes an
    experiment, not a table).
  - Uncertainty shown honestly: score *ranges* that visibly narrow as
    evidence accumulates.
- **Removed:** nothing visible; internally, the one-shot
  `build_from_assessment` path retires in favour of the evidence-stream path.
- **Why:** v3's loop runs on unvalidated self-reflection. v4 adds the two
  things that make movement believable — independent verification and
  visible uncertainty — which is also exactly what the school/parent buyer
  needs to pay for it.

### v5 — "Compound the loop" (the discovery graph)

*Job: every student's experiments make the next student's discovery cheaper.*

- **Stays:** everything student-facing.
- **Added:**
  - **Action efficacy data**: anonymized aggregation of which experiments
    most sharply discriminate fit for which hypothesis ("for 'doctor',
    hospital volunteering updates beliefs 4× more than biology videos") —
    the ranker's bonus hook consumes this the way it consumes affinity today.
  - **A marketplace of verified experiences** (workshops, micro-internships,
    shadowing) slotted into action cards — the monetization that doesn't
    corrupt the pedagogy, *if* ranked by measured efficacy rather than by
    who pays.
  - **Institutional views**: counsellor dashboards of cohort discovery
    momentum (not cohort "results").
- **Removed:** nothing; v5 is an aggregation layer.
- **Why:** this is where the moat hardens. Anyone can copy a quiz; nobody
  can copy three years of longitudinal action→outcome data across cohorts.
  The knowledge platform thesis ("the graph compounds") extends from careers
  to *experiments*: Detective Monkey ends up owning the map of which small
  actions reveal which futures — the category-defining asset.

---

## 4. MVP Reality Check — weeks, not years

The honest assessment: **the reposition is ~85% framing and ~15% new
machinery**, because the evidence pipeline, extraction, merging,
recalibration and action raw-material all exist. Four changes, in order:

1. **Reframe the surfaces (days).** Rename and re-copy: matches →
   "hypotheses worth testing"; add an evidence-strength pill next to every
   fit score (computed from the share of experiential vs self-report
   evidence — trivially derivable once source tags exist, and in the
   interim a static "based on self-report only" label is *honest and
   cheap*); growth card → momentum. Zero engine changes; this alone changes
   what the product *is* in a user's head.

2. **Action cards from existing data (days).** For each top-5 hypothesis,
   surface one smallest-next-action from the career's existing
   `portfolio_ideas`/`projects`/`youtube` fields with a time estimate and a
   "Start this experiment" button. Deterministic selection, no new AI, no
   new content authoring. `mentor.todays_action` already proves the
   pattern; this multiplies it per-hypothesis and makes it stateful
   (accepted / done / skipped — three states in the evidence repo).

3. **Close the loop (~1 week).** One endpoint + one screen: when a student
   marks an experiment done → 3 sliders + 1 open text → construct an
   `OpenResponse`, run the existing `extract_with_ai`/heuristic path, merge
   as a new high-weight evidence source, call the existing
   `_rebuild_intelligence` (affinity + intelligence profile refresh) → land
   the student on a **"here's what changed"** diff view (match scores
   before/after, which features moved, why). This diff moment *is the
   product*; everything else is furniture.

4. **Durable persistence (~1 week).** SQLite adapters behind
   `EvidenceProfileRepository` / profile / memory ports. Not a
   repositioning feature, but the loop is a lie without it — a longitudinal
   product cannot forget students on restart.

**Explicitly not in the MVP:** verified evidence, decay models, comparative
experiments, marketplaces, school dashboards, efficacy aggregation. All v4/v5.

**The MVP demo sentence:** *"She thought she wanted medicine. The app gave
her a two-hour experiment, she told it how it felt, and her map visibly
changed — and can show its reasoning."* If that demo lands with 20 students,
build v4. If students don't come back to reflect, you've learned the fatal
fact early and cheaply — which is itself the discovery philosophy, applied
to your own product.

---

## 5. Critical Review — the investor's view

**The elephant: engagement, not intelligence.** The vision's entire value
chain runs through a teenager voluntarily doing homework and coming back to
reflect. Career products have brutally episodic usage (2–3 touches per year
around decision deadlines), and discovery *increases* the effort asked.
There is currently **zero evidence** any student completes even one full
loop. Everything else about this vision is downstream of that number. An
alternative you haven't seriously considered: design *for* episodic use
(term-aligned "discovery sprints" tied to school calendars and stream-choice
deadlines) instead of fighting for weekly habit — the deadline is your
retention mechanic, and school assignment of experiments may matter more
than any streak system.

**The buyer contradiction is unresolved.** Students use it; parents and
schools pay; both buyers want *answers*. "Recommendations are hypotheses"
must be packaged as "evidence-backed confidence for the decision you must
make anyway by grade 11" or the sales motion fights the pedagogy. Relatedly:
Indian school sales are slow, relationship-driven, and counsellor-mediated —
there is no identified distribution channel in the current plan.

**The science is unvalidated.** No study — yours or anyone's — shows that
2-hour micro-experiences predict long-term career fit for adolescents. The
risk isn't that the loop does nothing; it's that it produces *authoritative-
feeling movement that is actually noise* — a horoscope with a progress bar.
Mitigations exist (confidence-weighted single samples, repeated trials,
comparative design, verified evidence) but they're v4, and the claim is
being made in v3.

**Cold-start content risk.** The action catalog is auto-derived from
knowledge-base fields never designed to be *assignments*. A vague or broken
first experiment ("do a portfolio project") kills trust instantly. Somebody
must QA the top ~50 hypotheses' actions by hand before launch.

**Competitive honesty.** Mindler, iDreamCareer, Univariety (India) and
Xello/YouScience (US) own the school-assessment budget line. The
differentiation — a living loop instead of a PDF — is real but must be
*visible in a 10-minute demo and in retention data*, because "our
architecture is evidence-native" is not a thing a school principal buys.

**Unvalidated assumptions, ranked by lethality:**
1. Students complete experiments and return to reflect (product-existential).
2. Reflection produces signal an extractor can use (garbage-in risk).
3. Schools/parents will pay for calibrated uncertainty over confident answers.
4. Auto-generated actions are good enough to start trust.
5. Micro-experience evidence actually predicts fit (the long-term science).

**Evidence I'd want before writing a cheque:** a 100-student, 8-week pilot
(one school, free) showing (a) ≥40% complete ≥2 full loops, (b) a non-trivial
**hypothesis-flip rate** — students who *changed or confirmed* a career
belief and can articulate the evidence (this is the money metric; it's the
testimonial parents repeat), (c) ≥2 counsellors who used the momentum
dashboard unprompted, and (d) one signed LOI at a real price. That's one
term of work with the MVP in §4.

**Also on the risk register:** you are steering minors' life decisions —
auditability and "we show our reasoning" (already architectural strengths)
should be marketed as safety features, and score movement from a single bad
day must be visibly damped.

---

## 6. The One Thing

**Make the completed discovery loop — not the recommendation, not the
profile — the atomic unit of the product, and adopt one north-star metric:
_validated discovery cycles per student per term_ (action completed →
reflection captured → belief measurably updated).**

Why this decision above all others:

1. **It forces every other right decision.** If cycles-per-term is the
   number everyone optimizes, then: persistence gets built (can't count
   cycles you forgot), the dashboard leads with the next experiment (that's
   where cycles start), scores grow evidence-strength labels (that's what a
   cycle updates), the pulse becomes per-action (that's what closes a
   cycle), sales collateral becomes momentum dashboards (that's what the
   metric shows a school), and the report becomes a cycle log. Each of
   those, decided independently, could drift back to the recommendation
   worldview; the metric makes drift visible immediately.

2. **It is the moat-building behaviour.** Every completed cycle is a row of
   longitudinal action→outcome data that no competitor and no LLM has. The
   current moat thesis (the knowledge graph) is real but rentable — O*NET is
   public and generation is cheap for anyone with an API key. Cycle data is
   *earned*, student-by-student, term-by-term, and compounds into v5's
   efficacy graph. The metric is literally counting moat accretion.

3. **It is falsifiable fast.** The gravest risk (§5, assumption 1) is that
   students won't loop. A north-star of cycles-per-term surfaces that truth
   in the first pilot term instead of after a year of building v4/v5 on an
   unvalidated foundation. If the number won't move above ~1, the company
   pivots to episodic sprint design (or to counsellor-mediated delivery)
   with most of the platform intact — the engines don't care how often the
   loop ticks.

4. **It resolves the identity question permanently.** "AI career
   recommendation tool" and "career discovery platform" stop being a
   philosophical debate and become an empirical one: a recommendation tool's
   cycle count is zero *by construction*. The day the metric exists,
   Detective Monkey is definitionally a discovery platform, and every
   feature proposal thereafter can be judged by one question — *does this
   create, improve, or count cycles?*

The engines you've built — evidence-with-provenance, confidence-weighted
merging, deterministic recalibration, the generated knowledge graph — were
always the right machinery for this product. The pivot isn't a rebuild. It's
finally pointing that machinery at the question it was built to answer: not
*"who are you?"* but *"what should you try next to find out?"*
