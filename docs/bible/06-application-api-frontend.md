# Chapter 6 — Application Layer, API & Frontend

## 6.1 The composition root (`application/container.py`)

`Backend.__init__` is the only file that knows concrete adapters: platform
services (clock, ids, env config), infrastructure (event bus, nine
repositories, vector index), provider selection (explicit injection wins →
`GEMINI_API_KEY` env → deterministic `TemplateLLMProvider`; `use_llm=False`
for pure-deterministic runs), ten engines, application services, and the
`KnowledgePlatform` sharing the same graph repository/bus/clock/LLM.
No DI framework, no globals: a test builds a full backend in one line; a
production deployment swaps adapters here and only here.

**Review.** Correct pattern at this scale. Two wishes: (a) `Backend` takes
`careers`/`insights` as constructor data — knowledge that should flow from
the Knowledge Platform instead (finding A-2); (b) provider selection logic
will grow — extract a `ProviderFactory` when a second LLM vendor lands. **P2.**

## 6.2 Application services & DTOs

Two service families:

- **P2 use-case services** (`services.py`): one class per use case
  (SubmitAssessment, GenerateProfile, GenerateRecommendations,
  ExplainRecommendation, AskAgent); each coordinates repositories + engines +
  bus, owns the transaction boundary, publishes events *after* persistence,
  and returns `ServiceResult` (ok/fail + `ErrorCode`) — services own no
  business rules.
- **IntelligenceApplicationService** (`intelligence_service.py`): the live
  product surface — build-from-assessment, dashboard, recommendations cards,
  career detail, roadmap, skill gap, comparison, coach, HTML report. It maps
  engine/mentor output into ~15 frozen DTO types (`intelligence_dto.py`);
  DTOs are the API's vocabulary and never leak domain objects.

**Envelope** (`envelope.py`): every response is
`{success, data, errors[], warnings[], metadata}` with `ErrorCode`→HTTP status
mapping. One shape for the frontend to handle; errors are data, not
exceptions.

⚠ **A-1:** the intelligence service accepts untyped constructor params
(`careers`, `students`, `profiles`, `insights: dict`) where the P2 services
take typed ports — tighten to the `Protocol` types; `insights` should be a
typed port over knowledge (see A-2). **P2.**
⚠ **A-2:** `career_insights: dict` is a parallel, seed-provided knowledge
store (salary, demand, roadmap steps per career) that duplicates what the
Knowledge Platform now owns. Target: an `InsightProvider` port implemented by
the platform (core facts from the graph; volatile facts via DynamicFacts),
deleting the seed dict. This is the same unification as W-2/M-3. **P1.**

## 6.3 API architecture — every endpoint's lifecycle

Controllers are thin (`rest/app.py`): parse → one service call → envelope.
Per the mandate, the uniform request lifecycle is: routing → path/body parse
(malformed → `VALIDATION_ERROR` envelope, no stack traces) → *(missing:
authn/z, §6.6)* → service (validation → engines → repositories → events) →
DTO → envelope → JSON. Observability today = engine metrics inside responses;
no access logs/tracing (Ch. 7).

| Endpoint | Service path | Notes |
|---|---|---|
| `GET /api/v1/health`, `/readyz` | — | liveness/readiness constants |
| `GET /api/v1/assessments/default` | seed definition | instrument as versioned data |
| `POST /students/{id}/assessment` | build_from_assessment | full trace: Ch. 2 §2.3 |
| `GET /students/{id}/dashboard` | dashboard | ranks + mentor derivations per call (W-1) |
| `GET /students/{id}/intelligence`, `/profile` | get_summary | same DTO, two routes |
| `POST`/`GET /students/{id}/recommendations` | recommend | both recompute (W-3) |
| `GET /students/{id}/careers/{cid}` | career_detail | insight + match + roadmap; sets mentor goal |
| `GET …/roadmap`, `…/skill-gap`, `/compare?a&b` | roadmap / skill_gap / compare | mentor derivations |
| `GET /students/{id}/report` | report_html | server-rendered self-contained HTML |
| `POST /conversations` | agent (+coach if student_id) | retrieval-grounded; Ch. 2 §2.3 step 6 |

⚠ **A-3:** knowledge-platform capabilities (ask/discover/compare/regional)
have no REST surface yet — add `/api/v1/knowledge/*` routes behind the same
envelope. **P1.** ⚠ **A-4:** no pagination/rate limits anywhere. **P2.**

## 6.4 Frontend architecture

A deliberately frameworkless SPA (`static/`: 40-line HTML shell, 335-line
`app.js`, token-driven CSS): hash-based view switching, `fetch` + envelope
handling, student id in `localStorage`, renders assessment → dashboard →
cards → detail → coach. **Why no framework:** the backend owns all logic and
all content; the frontend is a renderer, and a build-free SPA keeps the
zero-dependency ethos through the whole stack (`pip install` ships the UI).
**Trade-off accepted:** at the point the UI needs routing guards, offline
state, or component reuse across teams, adopt a build step (Vite + preact/
react) — the API envelope means the backend is untouched by that migration.
⚠ **A-5:** `localStorage` student identity is a placeholder for real auth
(§6.6) and report HTML interpolates strings server-side without escaping —
XSS risk the moment any user-influenced text reaches the report. Escape all
interpolations. **P1.**

## 6.5 Authentication & authorization — current state and required design

**Current state: none.** Any caller may read/write any student by path id;
acceptable only for the in-memory demo. This is finding **W-4 (P0)**.

**Required design (recommended, minimal-first):**
1. **Identity:** OIDC (Auth0/Cognito/Keycloak — any compliant IdP) with PKCE
   for the SPA; students are `sub` claims; guardians/counsellors are separate
   roles in the token. Password auth in-house is rejected — undifferentiated
   risk, and minors' accounts raise the stakes.
2. **AuthN middleware** at the FastAPI layer (adapter-only: verify JWT,
   inject `AuthenticatedPrincipal` into request state); the core stays
   framework-free by keeping the principal an application-layer value object.
3. **AuthZ:** resource-ownership checks in the application services
   (`principal.student_id == path student_id` or an explicit
   guardian/counsellor grant), not in controllers — services are the
   transaction boundary and must be safe against any transport. Role model:
   `student`, `guardian(of)`, `counsellor(org)`, `admin`, plus service tokens
   for background jobs.
4. **Consent gate:** assessment submission requires a recorded `Consent`
   aggregate (D-6); under-age flows require guardian consent — this is a
   *legal* requirement in most target markets, not an option.
5. **Transport:** TLS-terminating proxy, HSTS; API-key auth for
   server-to-server knowledge ingestion.

## 6.6 Design Review — application/API/frontend

| ID | Finding | Recommendation |
|----|---------|----------------|
| W-4 | No authn/authz (restated) | §6.5 design. **P0** |
| A-1 | Untyped service constructor params | Type against ports. **P2** |
| A-2 | `insights` dict duplicates knowledge | `InsightProvider` port on the platform. **P1** |
| A-3 | Knowledge platform unexposed via REST | `/api/v1/knowledge/*`. **P1** |
| A-4 | No pagination/rate limiting | Envelope-compatible cursors; proxy-level rate limits. **P2** |
| A-5 | Report-HTML string interpolation unescaped | `html.escape` all fields. **P1** |
| A-6 | `GET /recommendations` mutates nothing but recomputes; POST/GET asymmetry unclear | POST computes & persists (immutable aggregate), GET reads (W-3). **P1** |
