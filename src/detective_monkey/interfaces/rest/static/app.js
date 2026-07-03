// Detective Monkey — intelligent career companion SPA (UI_DASHBOARD_EVOLUTION).
// Presentation + flow only; all reasoning lives in the backend engines.
// The Student Evidence Engine powers the assessment; the dashboard is the
// student's career home.

const API = "/api/v1";
const view = document.getElementById("view");
const toastEl = document.getElementById("toast");

// ---- store (identity + exploration history) ------------------------------
const store = {
  get studentId() { return localStorage.getItem("dm.studentId"); },
  get name() { return localStorage.getItem("dm.name") || ""; },
  setStudent(name, id) { localStorage.setItem("dm.name", name); localStorage.setItem("dm.studentId", id); },
  reset() { ["dm.studentId", "dm.name", "dm.recent", "dm.saved", "dm.compared"].forEach((k) => localStorage.removeItem(k)); },
  _list(key) { try { return JSON.parse(localStorage.getItem(key) || "[]"); } catch { return []; } },
  _save(key, list) { localStorage.setItem(key, JSON.stringify(list.slice(0, 12))); },
  get recent() { return this._list("dm.recent"); },
  addRecent(id, name) { const l = this.recent.filter((c) => c.id !== id); l.unshift({ id, name }); this._save("dm.recent", l); },
  get saved() { return this._list("dm.saved"); },
  isSaved(id) { return this.saved.some((c) => c.id === id); },
  toggleSaved(id, name) {
    let l = this.saved;
    if (this.isSaved(id)) l = l.filter((c) => c.id !== id); else l.unshift({ id, name });
    this._save("dm.saved", l); return this.isSaved(id);
  },
  get compared() { return this._list("dm.compared"); },
  addCompared(a, b) { const l = this.compared.filter((p) => !(p.a === a && p.b === b)); l.unshift({ a, b }); this._save("dm.compared", l); },
};
function newStudentId(name) {
  const slug = (name || "student").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24) || "student";
  return `${slug}-${Math.random().toString(36).slice(2, 6)}`;
}

// ---- api ------------------------------------------------------------------
async function apiGet(p) { return (await fetch(API + p)).json(); }
async function apiPost(p, b) {
  return (await fetch(API + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) })).json();
}
const sid = () => store.studentId;
const envError = (e) => (e && e.errors && e.errors.length ? e.errors[0].message : "Something went wrong.");
const notFound = (e) => e && e.errors && e.errors[0] && e.errors[0].code === "NOT_FOUND";

// ---- helpers ----------------------------------------------------------------
let toastTimer;
function toast(m) { toastEl.textContent = m; toastEl.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => (toastEl.hidden = true), 2800); }
function el(h) { const t = document.createElement("template"); t.innerHTML = h.trim(); return t.content.firstElementChild; }
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function prettify(s) { return String(s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function pill(t, cls = "") { return `<span class="pill ${cls}">${escapeHtml(t)}</span>`; }
function list(items, cls = "") { return `<ul class="${cls}" style="margin:6px 0 0 18px">${(items || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`; }
function bar(label, value) { const p = Math.max(0, Math.min(100, value)); return `<div class="bar-row"><div class="bar-label"><span>${escapeHtml(label)}</span><span class="muted">${Math.round(p)}%</span></div><div class="bar-track"><div class="bar-fill" style="width:${p}%"></div></div></div>`; }
function skeleton(n = 4) { view.innerHTML = `<div class="card stack">${Array.from({ length: n }).map(() => `<div class="skeleton" style="width:${55 + Math.random() * 40}%"></div>`).join("")}</div>`; }
function errorCard(m) { return `<div class="card stack"><h1>Something went wrong</h1><p class="muted">${escapeHtml(m)}</p><div><button class="btn secondary" data-route="dashboard">Home</button></div></div>`; }
function fmtDate(iso) { if (!iso) return "—"; try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }); } catch { return "—"; } }
function metaGrid(pairs) {
  return `<div class="meta-grid">${pairs.map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${escapeHtml(v)}</div></div>`).join("")}</div>`;
}
function metaCard(title, pairs) { return `<div class="card"><h2>${title}</h2>${metaGrid(pairs)}</div>`; }

// Never show an empty page: universal empty-state with exploration options.
function emptyState(title, body) {
  return `<div class="card hero stack"><h1>${title}</h1><p>${body}</p>
    <div class="action-bar">
      <button class="btn" data-route="wizard">Take the assessment</button>
      <button class="btn secondary" data-route="explore">Explore industries</button>
      <button class="btn secondary" data-route="coach">Talk to the AI Coach</button>
      <button class="btn secondary" data-route="search">Browse careers</button>
    </div></div>`;
}

// ============================================================================
// DASHBOARD — the student's career home
// ============================================================================
async function renderDashboard() {
  if (!sid()) return renderOnboarding();
  skeleton(8);
  const [homeEnv, industriesEnv] = await Promise.all([
    apiGet(`/students/${sid()}/home`),
    apiGet("/careers/industries"),
  ]);
  const industries = industriesEnv.success ? industriesEnv.data : [];

  if (!homeEnv.success) {
    if (!notFound(homeEnv)) return void (view.innerHTML = errorCard(envError(homeEnv)));
    view.innerHTML =
      emptyState(`Welcome, ${escapeHtml(store.name || "explorer")}!`,
        "Your career companion is ready. Take the assessment to unlock your personalized dashboard — or start exploring right away.") +
      industriesSection(industries) + interestButtons();
    return;
  }

  const d = homeEnv.data;
  const w = d.welcome, s = d.snapshot;
  const continueRoute = w.validation_status === "pending" ? "validation" : "experiments";

  view.innerHTML = `
    ${welcomeCard(w, continueRoute)}
    ${d.pulse && d.pulse.available ? pulseBanner(d.pulse) : ""}
    ${nextExperimentCard(d.next_experiment)}
    ${snapshotCard(s)}
    ${matchesSection(d.matches)}
    ${momentumCard(d.momentum, d.growth)}
    <div class="grid grid-2">
      ${coachCard()}
      ${insightCard(d.insight)}
    </div>
    ${learningCard(d.learning)}
    ${continueExploringSection()}
    ${industriesSection(industries)}
    ${interestButtons()}`;
}

// ---- the discovery loop: next experiment ----------------------------------
function evidencePill(strength) {
  if (strength === undefined || strength === null) return "";
  return strength > 0
    ? pill(`🧪 evidence ${strength}%`, "tag-strength")
    : pill("self-report only", "");
}

function experimentActions(x) {
  if (x.status === "proposed") {
    return `<div class="action-bar">
      <button class="btn" data-xaccept="${x.id}">I'm in — start this</button>
      <button class="btn secondary" data-route="reflect" data-xid="${x.id}">I already did it</button>
      <button class="btn ghost" data-xskip="${x.id}">Swap for a different task</button></div>`;
  }
  if (x.status === "accepted") {
    return `<div class="action-bar">
      <button class="btn" data-route="reflect" data-xid="${x.id}">Done — tell me how it felt</button>
      <button class="btn ghost" data-xskip="${x.id}">Swap for a different task</button></div>`;
  }
  return "";
}

function experimentCard(x, { lead = false } = {}) {
  if (!x) return "";
  return `<div class="card ${lead ? "exp-lead" : ""}">
    ${lead ? `<div class="row" style="justify-content:space-between"><h2 style="margin:0">🧪 Your next experiment</h2>
      <button class="btn ghost" data-route="experiments">All experiments →</button></div>` : ""}
    <div class="row" style="margin:${lead ? "10px" : "0"} 0 4px">
      ${pill(x.career_name, "primary")}${pill("~" + x.minutes + " min")}${pill(x.tier_label)}${pill(prettify(x.modality))}
      ${x.status === "accepted" ? pill("in progress", "tag-strength") : ""}</div>
    <h3 style="margin:6px 0">${escapeHtml(x.title)}</h3>
    <p class="muted" style="margin:0 0 8px">${escapeHtml(x.brief)}</p>
    <details class="expand"><summary>Steps & why this task fits you</summary>
      <p style="margin:.5rem 0 .2rem"><strong>Steps</strong></p>${list(x.steps)}
      <p style="margin:.6rem 0 .2rem"><strong>Why this task, for you</strong></p>${list(x.why_this_task)}
      <p style="margin:.6rem 0 .2rem"><strong>What it tests</strong></p>
      <div class="row">${(x.tests || []).map((t) => pill(t)).join("")}</div>
    </details>
    ${experimentActions(x)}</div>`;
}

const nextExperimentCard = (x) => x ? experimentCard(x, { lead: true }) : "";

function momentumCard(m, growth) {
  if (!m) return growth ? "" : "";
  const todo = ((growth && growth.items) || []).filter((i) => !i.done);
  const stat = (n, label) => `<div class="tile" style="text-align:center"><div class="big">${n}</div><div class="label">${label}</div></div>`;
  return `<div class="card"><h2>🔄 Discovery momentum</h2>
    <p class="muted">Careers aren't chosen, they're discovered — one small experiment at a time.</p>
    <div class="grid grid-4">
      ${stat(m.cycles, "experiments completed")}
      ${stat(m.careers_tested, "careers tested")}
      ${stat(m.beliefs_updated, "beliefs updated")}
      ${stat(m.active + m.proposed, "waiting for you")}
    </div>
    ${todo.length ? `<details class="expand"><summary>Sharpen your evidence</summary>
      ${list(todo.map((i) => `${i.label} — ${i.detail}`))}</details>` : ""}
  </div>`;
}

function welcomeCard(w, continueRoute) {
  return `<div class="card hero">
    <h1>Hi ${escapeHtml(w.name || store.name)} 👋</h1>
    <div class="welcome-meta">
      ${w.grade ? `<div>Grade<b>${escapeHtml(w.grade)}</b></div>` : ""}
      ${w.school ? `<div>School<b>${escapeHtml(w.school)}</b></div>` : ""}
      <div>Career confidence<b>${w.career_confidence}%</b></div>
      <div>Last assessment<b>${fmtDate(w.last_assessment_at)}</b></div>
    </div>
    <div class="action-bar">
      <button class="btn" data-route="${continueRoute}">Continue your journey →</button>
      ${w.validation_status === "pending" ? pill("1 step left: confirm your profile") : ""}
    </div></div>`;
}

function pulseBanner(p) {
  return `<div class="card insight-card">
    <div class="rec"><div><h2>💓 Career Pulse available</h2>
      <p class="muted" style="margin:0">Six months since your last check-in — update your interests in about ${p.estimated_minutes} minutes.</p></div>
      <button class="btn" data-route="pulse">Start pulse</button></div></div>`;
}

function featureRows(items) {
  return (items || []).map((f) => `<div class="feature-row"><span class="name">${escapeHtml(f.label)}</span>${pill(f.score + "%", "primary")}</div>`).join("") || "<p class='muted'>—</p>";
}

function snapshotCard(s) {
  return `<div class="card"><h2>📸 Career snapshot</h2>
    <div class="snapshot-grid">
      <div class="snapshot-block"><h3>Top interests</h3>${featureRows(s.top_interests)}</div>
      <div class="snapshot-block"><h3>Top strengths</h3>${featureRows(s.top_strengths)}</div>
      <div class="snapshot-block"><h3>Profile</h3>
        <div class="feature-row"><span class="name">Work style</span>${pill(prettify(s.work_style || "—"))}</div>
        <div class="feature-row"><span class="name">Career confidence</span>${pill(s.career_confidence + "%", "primary")}</div>
        <div class="feature-row"><span class="name">Recommendation confidence</span>${pill(s.recommendation_confidence + "%", "primary")}</div>
        ${s.preferred_industries && s.preferred_industries.length ? `<div class="feature-row"><span class="name">Leaning towards</span></div><div class="row">${s.preferred_industries.map((i) => pill(i)).join("")}</div>` : ""}
      </div>
    </div>
    <div class="action-bar"><button class="btn ghost" data-route="assessment">See full assessment →</button></div></div>`;
}

function matchesSection(matches) {
  if (!matches || !matches.length) return "";
  const cards = matches.map((m) => `
    <div class="card clickable" data-route="career" data-cid="${m.career_id}">
      <div class="rec"><div>
        <h3 style="margin:0">${escapeHtml(m.name)}</h3>
        <p class="muted" style="margin:2px 0 6px;font-size:.85rem">${escapeHtml(m.industry_name || "")}</p>
        <div class="row" style="margin-bottom:6px">${evidencePill(m.evidence_strength)}</div>
        <p class="muted" style="margin:0;font-size:.88rem">${escapeHtml(m.why)}</p></div>
        <div class="score-badge">${m.score}%</div></div>
      <div class="action-bar">
        <button class="btn secondary" data-route="experiments">Test it</button>
        <button class="btn ghost" data-route="detail" data-cid="${m.career_id}">Explore</button></div>
    </div>`).join("");
  return `<div class="section-title"><h2>🎯 Career hypotheses — worth testing</h2>
      <button class="btn ghost" data-route="matches">View all →</button></div>
    <p class="muted" style="margin:-6px 0 10px">A match score is a hypothesis, not a verdict. Evidence comes from trying.</p>
    <div class="grid grid-2">${cards}</div>`;
}

function coachCard() {
  const quick = ["Ask about a career", "Compare two careers", "Find careers for my strengths", "Learning roadmap"];
  return `<div class="card"><h2>🤖 AI Coach</h2>
    <p class="muted">Your mentor knows your profile — ask anything.</p>
    <div class="chips">${quick.map((q) => `<button class="chip" data-route="coach" data-prompt="${escapeHtml(q)}">${escapeHtml(q)}</button>`).join("")}</div>
    <div class="action-bar"><button class="btn" data-route="coach">Open chat</button></div></div>`;
}

function insightCard(ins) {
  if (!ins) return "";
  return `<div class="card insight-card"><h2>💡 Career insight of the day</h2>
    <p><strong>${escapeHtml(ins.title)}</strong></p>
    <p class="muted">${escapeHtml(ins.detail)}</p>
    ${ins.career_id ? `<button class="btn ghost" data-route="career" data-cid="${ins.career_id}">Explore this career</button>` : ""}</div>`;
}

function learningCard(l) {
  if (!l || !l.for_career) return "";
  const block = (title, items) => items && items.length ? `<div class="snapshot-block"><h3>${title}</h3>${list(items)}</div>` : "";
  return `<div class="card"><h2>📚 Recommended learning</h2>
    <p class="muted">Curated for your top match — <strong>${escapeHtml(l.for_career)}</strong>.</p>
    <div class="snapshot-grid">
      ${block("Books", l.books)}${block("Courses", l.courses)}
      ${block("Projects", l.projects)}${block("Communities", l.communities)}
    </div></div>`;
}

function continueExploringSection() {
  const recent = store.recent.slice(0, 4), saved = store.saved.slice(0, 4), compared = store.compared.slice(0, 3);
  if (!recent.length && !saved.length && !compared.length) return "";
  const chipsOf = (items) => items.map((c) => `<button class="chip" data-route="career" data-cid="${c.id}">${escapeHtml(c.name)}</button>`).join("");
  return `<div class="card"><h2>🧭 Continue exploring</h2>
    ${recent.length ? `<h3>Recently viewed</h3><div class="chips" style="margin-bottom:10px">${chipsOf(recent)}</div>` : ""}
    ${saved.length ? `<h3>Saved careers</h3><div class="chips" style="margin-bottom:10px">${chipsOf(saved)}</div>` : ""}
    ${compared.length ? `<h3>Compared</h3><div class="chips">${compared.map((p) =>
      `<button class="chip" data-route="compare" data-a="${p.a}" data-b="${p.b}">${escapeHtml(p.a)} vs ${escapeHtml(p.b)}</button>`).join("")}</div>` : ""}
  </div>`;
}

function industriesSection(industries) {
  if (!industries || !industries.length) return "";
  const cards = industries.map((i) => `
    <div class="card clickable industry-card" data-route="industry" data-cid="${i.id}">
      <div class="icon">${i.icon}</div><h3>${escapeHtml(i.name)}</h3>
      <p class="muted">${escapeHtml(i.description)}</p>
      ${pill(`${i.career_count} careers`)}</div>`).join("");
  return `<div class="section-title"><h2>🏭 Explore industries</h2>
      <button class="btn ghost" data-route="explore">All industries →</button></div>
    <div class="grid grid-3">${cards}</div>`;
}

function interestButtons() {
  const interests = [["Technology", { q: "technology" }], ["Business", { q: "business" }],
    ["Healthcare", { q: "health" }], ["Science", { q: "science" }],
    ["Creative", { creativity: true }], ["Sports", { q: "sports" }],
    ["Government", { government: true }], ["Design", { q: "design" }]];
  return `<div class="card"><h2>✨ Explore by interest</h2><div class="chips">
    ${interests.map(([label, f]) => `<button class="chip" data-interest='${JSON.stringify(f)}'>${label}</button>`).join("")}
  </div></div>`;
}

// ---- onboarding -------------------------------------------------------------
function renderOnboarding() {
  view.innerHTML = `<div class="card hero stack"><h1>Meet your career companion 🐵</h1>
    <p>Detective Monkey helps you discover who you are, explore hundreds of careers,
       and build a path that actually fits you — with evidence, not guesswork.</p></div>
    <div class="card stack"><label for="name">What's your name?</label>
      <input id="name" type="text" placeholder="e.g. Sandeepan" />
      <div class="action-bar"><button class="btn" id="start">Start my journey →</button>
      <button class="btn secondary" data-route="explore">Just explore careers</button></div></div>`;
  const input = view.querySelector("#name"); input.focus();
  const start = () => {
    const name = input.value.trim();
    if (!name) { toast("Please enter your name."); return; }
    store.setStudent(name, newStudentId(name)); setRoute("wizard");
  };
  view.querySelector("#start").addEventListener("click", start);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") start(); });
}

// ============================================================================
// ASSESSMENT WIZARD — the Student Evidence Engine intake
// ============================================================================
const wizard = { def: null, step: 0, answers: {}, open: {}, profile: {}, goals: {}, academic: [] };

async function renderWizard() {
  if (!sid()) return renderOnboarding();
  if (!wizard.def) {
    skeleton(5);
    const env = await apiGet("/evidence/assessment");
    if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
    wizard.def = env.data; wizard.step = 0; wizard.answers = {}; wizard.open = {};
    wizard.profile = { name: store.name }; wizard.goals = {}; wizard.academic = [];
  }
  drawWizardStep();
}

function wizardSteps() { return 2 + wizard.def.sections.length; } // about + sections + goals

function stepDots() {
  const total = wizardSteps();
  return `<div class="step-dots">${Array.from({ length: total }).map((_, i) =>
    `<span class="${i < wizard.step ? "done" : i === wizard.step ? "now" : ""}"></span>`).join("")}</div>`;
}

function wizardNav(canBack, nextLabel) {
  return `<div class="wizard-nav">
    <button class="btn secondary" id="wz-back" ${canBack ? "" : "disabled"}>← Back</button>
    <button class="btn" id="wz-next">${nextLabel}</button></div>`;
}

function drawWizardStep() {
  const step = wizard.step;
  if (step === 0) return drawAboutStep();
  if (step <= wizard.def.sections.length) return drawSectionStep(wizard.def.sections[step - 1]);
  return drawGoalsStep();
}

function drawAboutStep() {
  const p = wizard.profile;
  const f = (id, label, placeholder, type = "text") => `<div class="field"><label for="${id}">${label}</label>
    <input id="${id}" type="${type}" value="${escapeHtml(p[id] || "")}" placeholder="${placeholder}" /></div>`;
  const academicRows = wizard.academic.map((a, i) => `
    <div class="row" data-acad="${i}" style="margin-bottom:8px">
      <input type="text" style="flex:2" placeholder="Subject" value="${escapeHtml(a.subject || "")}" data-k="subject" />
      <input type="number" style="flex:1" min="0" max="100" placeholder="Avg %" value="${a.average_score ?? ""}" data-k="average_score" />
      <select style="flex:1" data-k="trend">
        ${["stable", "improving", "declining"].map((t) => `<option value="${t}" ${a.trend === t ? "selected" : ""}>${prettify(t)}</option>`).join("")}
      </select>
      <button class="btn ghost" data-remove="${i}" title="Remove">✕</button></div>`).join("");
  view.innerHTML = `${stepDots()}
    <div class="card stack"><h1>About you</h1>
      <p class="muted">This helps personalize everything — only the basics, nothing more.</p>
      <div class="field-grid">
        ${f("name", "Name", "Your name")}${f("age", "Age", "e.g. 15", "number")}
        ${f("grade", "Grade / Class", "e.g. 10")}${f("school", "School", "Your school")}
        ${f("city", "City", "e.g. Guwahati")}${f("state", "State", "e.g. Assam")}
        ${f("country", "Country", "e.g. India")}${f("board", "Board", "e.g. CBSE")}
      </div></div>
    <div class="card stack"><h2>School marks <span class="muted" style="font-weight:400">(optional)</span></h2>
      <p class="muted">Add average scores per subject — or skip; you can import them later.</p>
      <div id="acad">${academicRows}</div>
      <div><button class="btn ghost" id="add-subject">+ Add subject</button></div></div>
    ${wizardNav(false, "Next →")}`;
  const save = () => {
    ["name", "age", "grade", "school", "city", "state", "country", "board"].forEach((k) => {
      const input = view.querySelector("#" + k); if (input) wizard.profile[k] = input.value.trim();
    });
    view.querySelectorAll("[data-acad]").forEach((row) => {
      const i = +row.dataset.acad;
      row.querySelectorAll("[data-k]").forEach((inp) => { wizard.academic[i][inp.dataset.k] = inp.value; });
    });
  };
  view.querySelector("#add-subject").addEventListener("click", () => { save(); wizard.academic.push({ trend: "stable" }); drawAboutStep(); });
  view.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => { save(); wizard.academic.splice(+b.dataset.remove, 1); drawAboutStep(); }));
  view.querySelector("#wz-next").addEventListener("click", () => {
    save();
    if (!wizard.profile.name) { toast("Please tell us your name."); return; }
    store.setStudent(wizard.profile.name, sid());
    wizard.step = 1; drawWizardStep(); window.scrollTo(0, 0);
  });
}

function drawSectionStep(section) {
  const qHtml = section.questions.map((q) => questionHtml(q)).join("");
  const answered = section.questions.filter((q) =>
    q.kind === "open" ? (wizard.open[q.id] || "").trim() : wizard.answers[q.id] !== undefined).length;
  view.innerHTML = `${stepDots()}
    <div class="card"><h1>${escapeHtml(section.title)}</h1>
      <p class="muted">${escapeHtml(section.intro)}</p>
      <p class="muted" style="font-size:.85rem">${answered}/${section.questions.length} answered — open questions are optional but make your profile much richer.</p></div>
    <div class="card">${qHtml}</div>
    ${wizardNav(true, wizard.step === wizard.def.sections.length ? "Next: your goals →" : "Next →")}`;
  bindQuestionEvents(section);
  view.querySelector("#wz-back").addEventListener("click", () => { wizard.step--; drawWizardStep(); window.scrollTo(0, 0); });
  view.querySelector("#wz-next").addEventListener("click", () => { wizard.step++; drawWizardStep(); window.scrollTo(0, 0); });
}

function questionHtml(q) {
  if (q.kind === "likert") {
    const val = wizard.answers[q.id];
    return `<div class="question" data-q="${q.id}"><p class="q-prompt">${escapeHtml(q.prompt)}</p>
      <div class="likert">${[1, 2, 3, 4, 5].map((v) =>
        `<button type="button" data-v="${v}" aria-pressed="${val === v}">${v}</button>`).join("")}</div>
      <div class="likert-ends"><span>Strongly disagree</span><span>Strongly agree</span></div></div>`;
  }
  if (q.kind === "open") {
    return `<div class="question" data-q="${q.id}"><p class="q-prompt">${escapeHtml(q.prompt)}</p>
      <textarea data-open="${q.id}" placeholder="A few sentences is perfect… (optional)">${escapeHtml(wizard.open[q.id] || "")}</textarea></div>`;
  }
  const selected = wizard.answers[q.id] || [];
  const multi = q.kind === "multi_choice";
  return `<div class="question" data-q="${q.id}"><p class="q-prompt">${escapeHtml(q.prompt)}</p>
    ${multi ? `<p class="muted" style="font-size:.82rem;margin:0 0 4px">Pick up to ${q.max_choices}</p>` : ""}
    <div class="options">${q.options.map((o) =>
      `<button type="button" class="option-btn" data-o="${o.id}" aria-pressed="${selected.includes(o.id)}">${escapeHtml(o.label)}</button>`).join("")}</div></div>`;
}

function bindQuestionEvents(section) {
  section.questions.forEach((q) => {
    const root = view.querySelector(`[data-q="${q.id}"]`);
    if (!root) return;
    if (q.kind === "likert") {
      root.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => {
        wizard.answers[q.id] = +b.dataset.v;
        root.querySelectorAll("[data-v]").forEach((x) => x.setAttribute("aria-pressed", x === b));
      }));
    } else if (q.kind === "open") {
      root.querySelector("textarea").addEventListener("input", (e) => { wizard.open[q.id] = e.target.value; });
    } else {
      const multi = q.kind === "multi_choice";
      root.querySelectorAll("[data-o]").forEach((b) => b.addEventListener("click", () => {
        let sel = wizard.answers[q.id] || [];
        if (multi) {
          if (sel.includes(b.dataset.o)) sel = sel.filter((x) => x !== b.dataset.o);
          else if (sel.length < q.max_choices) sel = [...sel, b.dataset.o];
          else { toast(`Pick at most ${q.max_choices}.`); return; }
        } else sel = [b.dataset.o];
        wizard.answers[q.id] = sel;
        root.querySelectorAll("[data-o]").forEach((x) => x.setAttribute("aria-pressed", sel.includes(x.dataset.o)));
      }));
    }
  });
}

function drawGoalsStep() {
  const g = wizard.goals;
  const chipSel = (id, options, value) => `<div class="chips" data-sel="${id}">${options.map((o) =>
    `<button type="button" class="chip ${value === o ? "on" : ""}" data-v="${o}">${prettify(o)}</button>`).join("")}</div>`;
  view.innerHTML = `${stepDots()}
    <div class="card stack"><h1>Your goals</h1>
      <p class="muted">These guide your matches — they never override the evidence.</p>
      <div class="field"><label>Dream career (if any)</label>
        <input id="g-dream" type="text" value="${escapeHtml(g.dream_career || "")}" placeholder="e.g. Game Designer — or leave blank" /></div>
      <div class="field"><label>Preferred country to work in</label>
        <input id="g-country" type="text" value="${escapeHtml(g.preferred_country || "")}" placeholder="e.g. India, Germany…" /></div>
      <div class="field"><label>Preferred work style</label>${chipSel("work_style", ["remote", "office", "field", "mixed"], g.preferred_work_style)}</div>
      <div class="field"><label>Government or private sector?</label>${chipSel("sector", ["government", "private", "either"], g.sector_preference)}</div>
      <div class="field"><label>Would you like to start your own venture someday?</label>${chipSel("entre", ["yes", "maybe", "no"], g.entrepreneurship_interest)}</div>
      <div class="field"><label>Willing to relocate for opportunity?</label>${chipSel("reloc", ["yes", "maybe", "no"], g.willing_to_relocate)}</div>
    </div>
    ${wizardNav(true, "Analyze my evidence ✨")}`;
  const selMap = { work_style: "preferred_work_style", sector: "sector_preference", entre: "entrepreneurship_interest", reloc: "willing_to_relocate" };
  Object.entries(selMap).forEach(([id, key]) => {
    view.querySelectorAll(`[data-sel="${id}"] .chip`).forEach((b) => b.addEventListener("click", () => {
      wizard.goals[key] = b.dataset.v;
      b.parentElement.querySelectorAll(".chip").forEach((x) => x.classList.toggle("on", x === b));
    }));
  });
  view.querySelector("#wz-back").addEventListener("click", () => { wizard.step--; drawWizardStep(); window.scrollTo(0, 0); });
  view.querySelector("#wz-next").addEventListener("click", submitWizard);
}

async function submitWizard() {
  wizard.goals.dream_career = view.querySelector("#g-dream").value.trim();
  wizard.goals.preferred_country = view.querySelector("#g-country").value.trim();

  const answers = Object.entries(wizard.answers).map(([question_id, v]) =>
    Array.isArray(v) ? { question_id, selected: v } : { question_id, value: v });
  if (!answers.length) { toast("Answer at least a few questions first."); return; }
  const open_answers = Object.entries(wizard.open)
    .filter(([, t]) => t && t.trim())
    .map(([question_id, text]) => ({ question_id, text: text.trim() }));

  const payload = {
    profile: wizard.profile,
    goals: wizard.goals,
    academic: wizard.academic.filter((a) => a.subject && a.average_score !== "" && a.average_score != null),
    answers, open_answers,
  };
  view.innerHTML = `<div class="card stack"><h1>Analyzing your evidence…</h1>
    <p class="muted">Scoring your answers, extracting features and building your profile.</p>
    <div class="skeleton" style="width:70%"></div><div class="skeleton" style="width:55%"></div><div class="skeleton" style="width:62%"></div></div>`;
  const r = await apiPost(`/students/${sid()}/evidence`, payload);
  if (!r.success) { view.innerHTML = errorCard(envError(r)); return; }
  wizard.def = null; // reset for potential retake
  toast("Your evidence profile is ready!");
  renderValidation(r.data.validation);
}

// ---- human-in-the-loop validation -------------------------------------------
async function renderValidation(validation) {
  if (!sid()) return renderOnboarding();
  if (!validation) {
    skeleton(4);
    const env = await apiGet(`/students/${sid()}/evidence`);
    if (!env.success) {
      if (notFound(env)) return void (view.innerHTML = emptyState("No profile yet", "Take the assessment first — it takes about 10 minutes."));
      return void (view.innerHTML = errorCard(envError(env)));
    }
    validation = env.data.validation;
  }
  const marked = new Set();
  const qualities = validation.qualities.map((q) => `
    <div class="quality-card" data-f="${q.feature}" role="button" tabindex="0" title="Tap if this doesn't sound like you">
      <div><strong>${escapeHtml(q.label)}</strong>
        <div class="evidence">${escapeHtml((q.evidence || [])[0] || "")}</div></div>
      ${pill(q.score + "%", "primary")}</div>`).join("");
  view.innerHTML = `<div class="card hero stack"><h1>Here's what the evidence says 🔍</h1>
    <p>Your strongest qualities, based on everything you shared. Tap any card that does <em>not</em> sound like you.</p></div>
    <div class="card">${qualities}
      <h2 style="margin-top:16px">${escapeHtml(validation.question)}</h2>
      <div class="action-bar">
        <button class="btn" data-verdict="yes">Yes, that's me</button>
        <button class="btn secondary" data-verdict="partially">Partially</button>
        <button class="btn secondary" data-verdict="no">Not really</button>
      </div></div>`;
  view.querySelectorAll(".quality-card").forEach((c) => {
    const toggle = () => { const f = c.dataset.f; marked.has(f) ? marked.delete(f) : marked.add(f); c.classList.toggle("off", marked.has(f)); };
    c.addEventListener("click", toggle);
    c.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  });
  view.querySelectorAll("[data-verdict]").forEach((b) => b.addEventListener("click", async () => {
    skeleton(3);
    const r = await apiPost(`/students/${sid()}/evidence/validation`,
      { verdict: b.dataset.verdict, inaccurate: [...marked] });
    if (!r.success) { view.innerHTML = errorCard(envError(r)); return; }
    toast(b.dataset.verdict === "yes" ? "Great — profile confirmed!" : "Thanks — we've adjusted your profile.");
    setRoute("dashboard");
  }));
}

// ---- Career Pulse -------------------------------------------------------------
async function renderPulse() {
  if (!sid()) return renderOnboarding();
  skeleton(4);
  const env = await apiGet(`/students/${sid()}/pulse`);
  if (!env.success) {
    if (notFound(env)) return void (view.innerHTML = emptyState("No profile yet", "The Career Pulse follows your first assessment."));
    return void (view.innerHTML = errorCard(envError(env)));
  }
  if (!env.data.available) {
    view.innerHTML = `<div class="card stack"><h1>💓 Career Pulse</h1>
      <p class="muted">Your next pulse check-in isn't due yet — we ask every six months so your profile stays fresh without repeating the full assessment.</p>
      <p class="muted">Last assessment: <strong>${fmtDate(env.data.last_assessment_at)}</strong>
      ${env.data.last_pulse_at ? ` · Last pulse: <strong>${fmtDate(env.data.last_pulse_at)}</strong>` : ""}</p>
      <div><button class="btn secondary" data-route="dashboard">Back to dashboard</button></div></div>`;
    return;
  }
  const section = env.data.definition.sections[0];
  const answers = {}, open = {};
  const draw = () => {
    view.innerHTML = `<div class="card"><h1>💓 ${escapeHtml(section.title)}</h1>
      <p class="muted">${escapeHtml(section.intro)}</p></div>
      <div class="card">${section.questions.map((q) => questionHtml(q)).join("")}</div>
      <div class="wizard-nav"><span></span><button class="btn" id="pulse-submit">Update my profile →</button></div>`;
    // Rebind against local state.
    section.questions.forEach((q) => {
      const root = view.querySelector(`[data-q="${q.id}"]`);
      if (q.kind === "likert") {
        root.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => {
          answers[q.id] = +b.dataset.v;
          root.querySelectorAll("[data-v]").forEach((x) => x.setAttribute("aria-pressed", x === b));
        }));
      } else if (q.kind === "open") {
        root.querySelector("textarea").addEventListener("input", (e) => { open[q.id] = e.target.value; });
      } else {
        root.querySelectorAll("[data-o]").forEach((b) => b.addEventListener("click", () => {
          answers[q.id] = [b.dataset.o];
          root.querySelectorAll("[data-o]").forEach((x) => x.setAttribute("aria-pressed", x === b));
        }));
      }
    });
    view.querySelector("#pulse-submit").addEventListener("click", async () => {
      const body = {
        answers: Object.entries(answers).map(([question_id, v]) => Array.isArray(v) ? { question_id, selected: v } : { question_id, value: v }),
        open_answers: Object.entries(open).filter(([, t]) => t && t.trim()).map(([question_id, text]) => ({ question_id, text: text.trim() })),
      };
      if (!body.answers.length && !body.open_answers.length) { toast("Answer at least one question."); return; }
      skeleton(3);
      const r = await apiPost(`/students/${sid()}/pulse`, body);
      if (!r.success) { view.innerHTML = errorCard(envError(r)); return; }
      toast("Pulse recorded — your profile is refreshed!");
      setRoute("dashboard");
    });
  };
  // Reuse wizard state holders safely.
  const saved = { a: wizard.answers, o: wizard.open };
  wizard.answers = answers; wizard.open = open;
  draw();
  wizard.answers = saved.a; wizard.open = saved.o;
}

// ============================================================================
// EXPERIMENTS — the discovery loop
// ============================================================================
async function renderExperiments() {
  if (!sid()) return renderOnboarding();
  skeleton(5);
  const env = await apiGet(`/students/${sid()}/experiments`);
  if (!env.success) {
    if (notFound(env)) return void (view.innerHTML = emptyState("Experiments unlock after your assessment",
      "First we build your hypotheses; then you get small, personal experiments to test them."));
    return void (view.innerHTML = errorCard(envError(env)));
  }
  const d = env.data;
  const completed = d.completed.map((x) => `<div class="card">
    <div class="row" style="margin-bottom:4px">${pill(x.career_name, "primary")}${pill(prettify(x.modality))}
      ${x.reflection ? pill(`enjoyed ${x.reflection.enjoyment}/5`, x.reflection.enjoyment >= 3.5 ? "tag-strength" : "tag-gap") : ""}</div>
    <h3 style="margin:4px 0">${escapeHtml(x.title)}</h3>
    ${x.score_moves.length ? `<div class="row">${x.score_moves.slice(0, 3).map((m) =>
      deltaPill(m.career, m.before, m.after)).join("")}</div>` : "<p class='muted' style='margin:0'>No belief moved — that's evidence too.</p>"}
  </div>`).join("");
  view.innerHTML = `
    <div class="card hero stack"><h1>🧪 My Experiments</h1>
      <p>Small, real-world tests of your career hypotheses — sized for you. Every one you finish makes your map sharper.</p></div>
    ${momentumCard(d.momentum, null)}
    ${d.active.length ? `<div class="section-title"><h2>In progress</h2></div>` + d.active.map((x) => experimentCard(x)).join("") : ""}
    <div class="section-title"><h2>Proposed for you</h2></div>
    ${d.proposed.map((x) => experimentCard(x)).join("") || "<div class='card'><p class='muted'>Nothing proposed right now — check back after your matches update.</p></div>"}
    ${completed ? `<div class="section-title"><h2>Completed — your evidence trail</h2></div>` + completed : ""}`;
}

function deltaPill(label, before, after) {
  const delta = Math.round((after - before) * 10) / 10;
  const cls = delta > 0 ? "tag-strength" : delta < 0 ? "tag-gap" : "";
  const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "→";
  return pill(`${label}: ${Math.round(before)}% ${arrow} ${Math.round(after)}%`, cls);
}

async function experimentAction(url, okMessage) {
  const r = await apiPost(url, {});
  if (!r.success) { toast(envError(r)); return null; }
  if (okMessage) toast(okMessage);
  return r.data;
}

// ---- reflection: close one discovery cycle ----------------------------------
async function renderReflect(xid) {
  if (!sid()) return renderOnboarding();
  skeleton(4);
  const env = await apiGet(`/students/${sid()}/experiments`);
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const all = [...env.data.active, ...env.data.proposed, ...env.data.completed];
  const x = all.find((e) => e.id === xid);
  if (!x) return void (view.innerHTML = errorCard("Experiment not found."));
  if (x.status === "completed") { toast("Already reflected on this one."); return renderExperiments(); }

  const answers = { enjoyment: 0, energy: 0, would_do_again: 0 };
  const scale = (key, question, low, high) => `<div class="question" data-scale="${key}">
    <p class="q-prompt">${question}</p>
    <div class="likert">${[1, 2, 3, 4, 5].map((v) => `<button type="button" data-v="${v}">${v}</button>`).join("")}</div>
    <div class="likert-ends"><span>${low}</span><span>${high}</span></div></div>`;
  view.innerHTML = `
    <div class="card hero stack"><h1>How did it feel?</h1>
      <p>${escapeHtml(x.title)} — ${escapeHtml(x.career_name)}. Two minutes of honesty; loving it and hating it are equally useful evidence.</p></div>
    <div class="card">
      ${scale("enjoyment", "How much did you enjoy it?", "Not at all", "Loved it")}
      ${scale("energy", "How did it leave you feeling?", "Drained", "Energized")}
      ${scale("would_do_again", "Would you do something like this again?", "Never", "Absolutely")}
      <div class="question"><p class="q-prompt">What stood out? <span class="muted" style="font-weight:400">(optional, but this is where the good evidence lives)</span></p>
        <textarea id="reflect-text" placeholder="The moment I got absorbed was… / I gave up when… / I was surprised that…"></textarea></div>
      <div class="wizard-nav"><button class="btn secondary" data-route="experiments">← Back</button>
        <button class="btn" id="reflect-submit">Update my map ✨</button></div></div>`;
  view.querySelectorAll("[data-scale]").forEach((root) => {
    root.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => {
      answers[root.dataset.scale] = +b.dataset.v;
      root.querySelectorAll("[data-v]").forEach((k) => k.setAttribute("aria-pressed", k === b));
    }));
  });
  view.querySelector("#reflect-submit").addEventListener("click", async () => {
    if (!answers.enjoyment || !answers.energy || !answers.would_do_again) {
      toast("Answer the three scales first."); return;
    }
    const text = view.querySelector("#reflect-text").value.trim();
    view.innerHTML = `<div class="card stack"><h1>Recalibrating your map…</h1>
      <p class="muted">Folding your experience into the evidence and re-ranking your hypotheses.</p>
      <div class="skeleton" style="width:70%"></div><div class="skeleton" style="width:50%"></div></div>`;
    const r = await apiPost(`/students/${sid()}/experiments/${xid}/complete`, { ...answers, text });
    if (!r.success) { view.innerHTML = errorCard(envError(r)); return; }
    renderDiff(r.data);
  });
}

// ---- "here's what changed" — the heart of the loop ---------------------------
function renderDiff(d) {
  const x = d.experiment;
  const moves = d.career_moves.map((m) => `<div class="feature-row">
    <span class="name">${escapeHtml(m.career)}</span>
    <span class="${m.delta > 0 ? "delta-up" : m.delta < 0 ? "delta-down" : "muted"}">
      ${Math.round(m.before)}% ${m.delta > 0 ? "▲" : m.delta < 0 ? "▼" : "→"} ${Math.round(m.after)}%
      (${m.delta > 0 ? "+" : ""}${m.delta})</span></div>`).join("");
  const feats = d.feature_moves.map((f) => `<div class="feature-row">
    <span class="name">${escapeHtml(f.feature)}</span>
    <span class="${f.after > f.before ? "delta-up" : f.after < f.before ? "delta-down" : "muted"}">${f.before}% → ${f.after}%</span></div>`).join("");
  const es = d.evidence_strength;
  view.innerHTML = `
    <div class="card hero stack"><h1>Your map moved 🗺️</h1>
      <p>You tested <strong>${escapeHtml(x.career_name)}</strong> with a real experiment.
      That's evidence no quiz can give you — here's what it changed.</p></div>
    <div class="grid grid-2">
      <div class="card"><h2>Career hypotheses</h2>${moves || "<p class='muted'>No scores moved this time — steady beliefs are evidence too.</p>"}</div>
      <div class="card"><h2>What we learned about you</h2>${feats || "<p class='muted'>No features shifted.</p>"}
        <div style="margin-top:10px">${bar(`Evidence strength — ${es.career}`, es.after)}
        <p class="muted" style="font-size:.85rem;margin:2px 0 0">was ${es.before}% before this experiment</p></div></div>
    </div>
    ${momentumCard(d.momentum, null)}
    ${d.next_experiment ? experimentCard(d.next_experiment, { lead: true }) : ""}
    <div class="action-bar">
      <button class="btn" data-route="dashboard">Back to dashboard</button>
      <button class="btn secondary" data-route="matches">See all hypotheses</button></div>`;
  window.scrollTo(0, 0);
}

// ============================================================================
// MY ASSESSMENT — the evidence profile, readable
// ============================================================================
async function renderAssessment() {
  if (!sid()) return renderOnboarding();
  skeleton(6);
  const [evEnv, dashEnv] = await Promise.all([
    apiGet(`/students/${sid()}/evidence`),
    apiGet(`/students/${sid()}/dashboard`),
  ]);
  if (!evEnv.success) {
    if (notFound(evEnv)) return void (view.innerHTML = emptyState("Your assessment awaits",
      "40 conversational questions — about 10 minutes — and your evidence-based career profile is ready."));
    return void (view.innerHTML = errorCard(envError(evEnv)));
  }
  const d = evEnv.data, s = d.snapshot, dash = dashEnv.success ? dashEnv.data : null;
  const featureBars = Object.entries(d.extracted_features)
    .sort((a, b) => b[1].score - a[1].score)
    .map(([name, f]) => `<details class="expand"><summary>${prettify(name)} — ${Math.round(f.score * 100)}%</summary>
      ${bar("score", f.score * 100)}${bar("confidence", f.confidence * 100)}
      ${list(f.evidence)}</details>`).join("");
  view.innerHTML = `
    <div class="card hero stack"><h1>📊 My Assessment</h1>
      <p>Completed ${fmtDate(d.metadata.created_at)} · ${d.assessment.structured_answered}/${d.assessment.structured_total} structured
      + ${d.assessment.open_answered}/${d.assessment.open_total} open questions · Sources: ${(d.metadata.sources_used || []).join(", ")}</p>
      <div class="action-bar">
        <button class="btn" data-route="wizard">Retake assessment</button>
        <button class="btn secondary" data-route="pulse">Career Pulse</button>
        ${d.validation.status === "pending" ? `<button class="btn secondary" data-route="validation">Confirm your profile</button>` : ""}
      </div></div>
    ${snapshotCard(s)}
    ${dash ? `<div class="grid grid-2">
      <div class="card"><h2>Career readiness</h2>
        <div class="readiness-ring"><div class="ring" style="--p:${dash.readiness.score}"><span>${dash.readiness.score}%</span></div>
        <div><strong>${escapeHtml(dash.readiness.level)}</strong><p class="muted" style="margin:4px 0">${escapeHtml(dash.readiness.explanation)}</p></div></div></div>
      <div class="card"><h2>Learning style</h2>
        <p style="font-size:1.4rem;color:var(--color-primary);font-weight:800;margin:0">${prettify(dash.learning_style.style)}</p>
        <p class="muted">${escapeHtml(dash.learning_style.explanation)}</p>
        <h2 style="margin-top:12px">Personality summary</h2>
        <p class="muted">${escapeHtml(dash.ai_summary)}</p></div>
    </div>` : ""}
    <div class="card"><h2>🧾 Evidence summary</h2>
      <p class="muted">Every feature carries a score, a confidence and the evidence behind it — expand to see why.</p>
      ${featureBars}</div>
    <div class="card"><h2>Work preferences & values</h2>
      ${metaGrid([["Work style", prettify(s.work_style || "—")],
        ["Dream career", d.goals.dream_career || "—"],
        ["Preferred country", d.goals.preferred_country || "—"],
        ["Sector", prettify(d.goals.sector_preference || "—")],
        ["Own venture?", prettify(d.goals.entrepreneurship_interest || "—")],
        ["Relocate?", prettify(d.goals.willing_to_relocate || "—")]])}</div>`;
}

// ============================================================================
// MY CAREER MATCHES
// ============================================================================
function premiumCard(c) {
  const skills = c.skill_gaps.map((s) => prettify(s));
  const saved = store.isSaved(c.career_id);
  const hyp = (window.__hypStrength || {})[c.career_id];
  return el(`<div class="card">
    <div class="rec"><div><h2 style="margin:0">${escapeHtml(c.name)}</h2>
      ${hyp ? evidencePill(hyp.strength) : ""}
      ${hyp && hyp.runs ? pill(`${hyp.runs} experiment(s) run`, "primary") : ""}
      ${pill(`confidence ${Math.round(c.confidence * 100)}%`)}
      ${skills.length ? pill(`${skills.length} skill gap(s)`) : pill("ready now", "tag-strength")}</div>
      <div class="score-badge">${Math.round(c.score)}%</div></div>
    <p class="muted">${escapeHtml(c.summary)}</p>
    ${metaGrid([["Salary", c.salary_range], ["Demand", c.future_demand], ["Automation risk", c.automation_risk], ["Remote", c.remote_compatibility], ["Learning time", c.estimated_learning_weeks + " wks"]])}
    <h3 style="margin:.4rem 0 .2rem">Why this matches you</h3>${list(c.match_explanation)}
    <details class="expand"><summary>Strengths used, challenges & evidence</summary>
      <p style="margin:.4rem 0"><strong>Strengths used</strong></p><div class="row">${c.strengths_used.map((s) => pill(s, "tag-strength")).join("")}</div>
      <p style="margin:.6rem 0 .2rem"><strong>Potential challenges</strong></p>${list(c.challenges)}
      ${c.skill_gaps.length ? `<p style="margin:.6rem 0 .2rem"><strong>Skill gaps</strong></p><div class="row">${c.skill_gaps.map((s) => pill(prettify(s), "tag-gap")).join("")}</div>` : ""}
      <p style="margin:.6rem 0 .2rem"><strong>Required education</strong></p>${list(c.required_education)}
      ${c.evidence.length ? `<p style="margin:.6rem 0 .2rem"><strong>Evidence used</strong></p>${list(c.evidence.map((e) => `${e.claim} — ${e.source}`))}` : ""}
    </details>
    <div class="action-bar">
      <button class="btn" data-route="career" data-cid="${c.career_id}">Explore career</button>
      <button class="btn secondary" data-route="roadmap" data-cid="${c.career_id}">Roadmap</button>
      <button class="btn secondary" data-route="skillgap" data-cid="${c.career_id}">Skill gap</button>
      <button class="btn secondary" data-route="compare" data-a="${c.career_id}">Compare</button>
      <button class="btn ghost" data-save="${c.career_id}" data-name="${escapeHtml(c.name)}">${saved ? "★ Saved" : "☆ Save"}</button>
    </div></div>`);
}

async function renderMatches() {
  if (!sid()) return renderOnboarding();
  skeleton(5);
  const [env, hypEnv] = await Promise.all([
    apiPost(`/students/${sid()}/recommendations`, {}),
    apiGet(`/students/${sid()}/hypotheses`),
  ]);
  if (!env.success) {
    if (notFound(env)) return void (view.innerHTML = emptyState("No hypotheses yet",
      "Your career hypotheses are generated from your evidence profile — take the assessment to unlock them."));
    return void (view.innerHTML = errorCard(envError(env)));
  }
  const strengthById = {};
  if (hypEnv.success) hypEnv.data.hypotheses.forEach((h) => {
    strengthById[h.career_id] = { strength: h.evidence_strength, runs: h.experiments_run };
  });
  window.__hypStrength = strengthById;
  const cards = env.data.cards || [];
  view.innerHTML = `<div class="card stack"><h1>🎯 Career Hypotheses</h1>
    <p class="muted">These are <strong>hypotheses, not verdicts</strong> — ranked from your evidence, waiting to be tested.
    A score changes when you actually try things; that's the point.</p>
    <div class="action-bar"><button class="btn" data-route="experiments">🧪 Test them with experiments</button>
      <button class="btn secondary" data-route="compare">Compare careers</button>
      <a class="btn secondary" href="${API}/students/${sid()}/report" target="_blank" rel="noopener">Download report</a></div></div>
    <div id="recs"></div>`;
  const c = view.querySelector("#recs");
  if (!cards.length) { c.innerHTML = emptyState("No matches yet", "Explore industries while we gather more evidence."); return; }
  const PAGE = 10;
  let shown = 0;
  const showMore = el(`<div class="action-bar" style="justify-content:center"><button class="btn secondary">Show more matches</button></div>`);
  const renderPage = () => {
    cards.slice(shown, shown + PAGE).forEach((m) => c.insertBefore(premiumCard(m), showMore));
    shown += PAGE;
    if (shown >= cards.length) showMore.remove();
  };
  c.appendChild(showMore);
  showMore.querySelector("button").addEventListener("click", renderPage);
  renderPage();
}

// ---- personal career detail / roadmap / skill gap -----------------------------
async function renderDetail(cid) {
  if (!sid()) return renderCareerProfile(cid);
  skeleton(6);
  const env = await apiGet(`/students/${sid()}/careers/${cid}`);
  if (!env.success) return renderCareerProfile(cid);
  const d = env.data;
  view.innerHTML = `
    <div class="card hero stack"><h1>${escapeHtml(d.name)}</h1>
      <p>${escapeHtml(d.overview)}</p>${pill(`${Math.round(d.compatibility)}% personal compatibility`)}</div>
    <div class="card"><h2>Why it fits you</h2><p>${escapeHtml(d.personal_note)}</p></div>
    ${metaCard("Snapshot", [["Salary", d.salary_range], ["Demand", d.demand], ["Future outlook", d.future_outlook], ["Automation risk", d.automation_risk], ["Remote", d.remote_compatibility]])}
    <div class="grid grid-2">
      <div class="card"><h2>A day in the role</h2>${list(d.daily_work)}</div>
      <div class="card"><h2>Responsibilities</h2>${list(d.responsibilities)}</div></div>
    <div class="card"><h2>Career progression</h2>${list(d.progression.map(([t, yrs]) => `${t} (${yrs})`))}</div>
    <div class="grid grid-2">
      <div class="card"><h2>Education</h2>${list(d.required_education)}</div>
      <div class="card"><h2>Recommended certifications</h2>${list(d.certifications)}</div></div>
    ${roadmapCard(d.roadmap)}
    <div class="action-bar">
      <button class="btn" data-route="career" data-cid="${cid}">Full career encyclopedia page</button>
      <button class="btn secondary" data-route="skillgap" data-cid="${cid}">See skill gap</button>
      <button class="btn secondary" data-route="matches">← Back to matches</button></div>`;
}

function roadmapCard(rm) {
  const steps = rm.steps.map((s) => `<li class="${s.status}"><strong>${escapeHtml(s.title)}</strong>
    <div class="row" style="margin-top:4px">${pill(s.duration)}${pill("difficulty: " + s.difficulty)}${pill(s.importance)}${pill(prettify(s.status), s.status === "in_progress" ? "tag-strength" : "")}</div></li>`).join("");
  return `<div class="card"><h2>Roadmap — ${escapeHtml(rm.goal)}</h2><ul class="timeline">${steps}</ul></div>`;
}
async function renderRoadmap(cid) {
  if (!sid()) return renderOnboarding();
  skeleton(5);
  const env = await apiGet(`/students/${sid()}/careers/${cid}/roadmap`);
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  view.innerHTML = roadmapCard(env.data) + `<div class="action-bar"><button class="btn secondary" data-route="detail" data-cid="${cid}">Career detail</button></div>`;
}

async function renderSkillGap(cid) {
  if (!sid()) return renderOnboarding();
  skeleton(4);
  const env = await apiGet(`/students/${sid()}/careers/${cid}/skill-gap`);
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const g = env.data;
  const missing = g.missing.map((m) => `<div class="card" style="padding:12px 16px;margin:8px 0">
    <div class="rec"><strong>${escapeHtml(prettify(m.name))}</strong>${pill(m.importance, "tag-gap")}</div>
    <div class="row">${pill(`~${m.weeks} weeks`)}${pill(`+${m.employability_gain}% compatibility`)}</div></div>`).join("");
  view.innerHTML = `<div class="card stack"><h1>Skill gap — ${escapeHtml(g.name)}</h1>
    ${bar("Current compatibility", g.current_compatibility)}
    ${bar("Projected after learning", g.projected_compatibility)}</div>
    <div class="card"><h2>You already bring</h2><div class="row">${g.strengths.map((s) => pill(s, "tag-strength")).join("") || "<span class='muted'>—</span>"}</div></div>
    <div class="card"><h2>Skills to develop</h2>${missing || "<p class='muted'>You're ready for this role!</p>"}</div>
    <div class="action-bar"><button class="btn" data-route="roadmap" data-cid="${cid}">See learning roadmap</button></div>`;
}

// ---- comparison ---------------------------------------------------------------
async function renderCompare(params = {}) {
  if (!sid()) return renderOnboarding();
  skeleton(4);
  const env = await apiPost(`/students/${sid()}/recommendations`, {});
  if (!env.success) {
    if (notFound(env)) return void (view.innerHTML = emptyState("Compare needs a profile", "Take the assessment first, then compare any two careers side by side."));
    return void (view.innerHTML = errorCard(envError(env)));
  }
  const cards = env.data.cards || [];
  const opts = cards.map((c) => `<option value="${c.career_id}">${escapeHtml(c.name)}</option>`).join("");
  view.innerHTML = `<div class="card stack"><h1>⚖️ Compare careers</h1>
    <div class="row"><select id="a">${opts}</select><span>vs</span><select id="b">${opts}</select>
      <button class="btn" id="go">Compare</button></div></div><div id="out"></div>`;
  if (params.a) view.querySelector("#a").value = params.a;
  if (params.b) view.querySelector("#b").value = params.b;
  else if (cards[1]) view.querySelector("#b").value = cards[1].career_id;
  view.querySelector("#go").addEventListener("click", async () => {
    const a = view.querySelector("#a").value, b = view.querySelector("#b").value;
    if (a === b) { toast("Pick two different careers."); return; }
    store.addCompared(a, b);
    const r = await apiGet(`/students/${sid()}/compare?a=${a}&b=${b}`);
    const out = view.querySelector("#out");
    if (!r.success) { out.innerHTML = errorCard(envError(r)); return; }
    const d = r.data;
    const rows = d.rows.map((row) => `<tr><td>${escapeHtml(row.dimension)}</td>
      <td class="${row.winner === "a" ? "win" : ""}">${escapeHtml(row.a)}</td>
      <td class="${row.winner === "b" ? "win" : ""}">${escapeHtml(row.b)}</td></tr>`).join("");
    out.innerHTML = `<div class="card"><table class="cmp"><thead><tr><th></th><th>${escapeHtml(d.career_a)}</th><th>${escapeHtml(d.career_b)}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="card hero"><h2>AI recommendation</h2><p style="margin:0">${escapeHtml(d.recommendation)}</p></div>`;
  });
  view.querySelector("#go").click();
}

// ============================================================================
// AI COACH
// ============================================================================
const COACH_PROMPTS = ["Explain this career to me", "Compare two careers for me", "Suggest alternatives to my top match",
  "Best universities for my goal", "Build me a career roadmap", "Jobs in my state", "Jobs abroad",
  "Scholarships I should know about", "Learning resources for my top match"];

async function renderCoach(params = {}) {
  view.innerHTML = `<div class="card"><h1>🤖 AI Coach</h1>
    <p class="muted">${sid() ? "I know your profile, strengths and matches — ask me anything." : "Ask me about any career — take the assessment for personalized answers."}</p></div>
    <div class="card"><div class="chat-log" id="log"></div>
      <div class="chips" id="chips"></div>
      <form class="chat-form" id="chat"><input id="msg" type="text" placeholder="Ask your coach…" aria-label="Message" /><button class="btn" type="submit">Send</button></form></div>`;
  const log = view.querySelector("#log");
  const chips = view.querySelector("#chips");
  const add = (t, who) => { log.appendChild(el(`<div class="msg ${who}">${escapeHtml(t)}</div>`)); log.scrollTop = log.scrollHeight; };
  add("Hi! What would you like to work on today?", "bot");

  async function send(message) {
    if (!message.trim()) return;
    add(message, "user");
    const r = await apiPost("/conversations", { message, student_id: sid() || undefined });
    const data = r.success ? r.data : null;
    add(data ? (data.response || data.reply || "") : envError(r), "bot");
    if (data && data.suggestions && data.suggestions.length) renderChips(data.suggestions);
  }
  function renderChips(qs) {
    chips.innerHTML = "";
    (qs || []).forEach((q) => { const b = el(`<button class="chip" type="button">${escapeHtml(q)}</button>`); b.addEventListener("click", () => send(q)); chips.appendChild(b); });
  }
  renderChips(COACH_PROMPTS.slice(0, 6));
  if (sid()) {
    apiGet(`/students/${sid()}/dashboard`).then((dash) => {
      if (dash.success && dash.data.suggested_questions) renderChips([...dash.data.suggested_questions, ...COACH_PROMPTS.slice(0, 4)]);
    });
  }
  view.querySelector("#chat").addEventListener("submit", (e) => { e.preventDefault(); const i = view.querySelector("#msg"); const m = i.value; i.value = ""; i.focus(); send(m); });
  if (params.prompt) send(params.prompt);
}

// ============================================================================
// MY PROFILE
// ============================================================================
async function renderProfile() {
  if (!sid()) return renderOnboarding();
  skeleton(5);
  const env = await apiGet(`/students/${sid()}/evidence`);
  if (!env.success) {
    if (notFound(env)) return void (view.innerHTML = emptyState(`👤 ${escapeHtml(store.name || "My Profile")}`,
      "Your profile fills up as you take the assessment and explore careers."));
    return void (view.innerHTML = errorCard(envError(env)));
  }
  const d = env.data, p = d.profile;
  const saved = store.saved;
  const growth = growthFromEvidence(d);
  view.innerHTML = `
    <div class="card hero stack"><h1>👤 ${escapeHtml(p.name || store.name)}</h1>
      <p>${[p.grade && `Grade ${p.grade}`, p.school, [p.city, p.state, p.country].filter(Boolean).join(", ")].filter(Boolean).join(" · ") || "Student explorer"}</p></div>
    ${metaCard("Basic information", [["Name", p.name || "—"], ["Age", p.age ?? "—"], ["Grade", p.grade || "—"],
      ["School", p.school || "—"], ["City", p.city || "—"], ["State", p.state || "—"],
      ["Country", p.country || "—"], ["Board", p.board || "—"]])}
    <div class="card"><h2>Academic information</h2>
      ${d.academic.length ? d.academic.map((a) => bar(`${a.subject}${a.trend !== "stable" ? ` (${a.trend})` : ""}`, a.average_score)).join("") : "<p class='muted'>No academic records yet — retake the assessment to add your marks.</p>"}</div>
    ${metaCard("Career goals", [["Dream career", d.goals.dream_career || "—"], ["Preferred country", d.goals.preferred_country || "—"],
      ["Work style", prettify(d.goals.preferred_work_style || "—")], ["Sector", prettify(d.goals.sector_preference || "—")],
      ["Own venture?", prettify(d.goals.entrepreneurship_interest || "—")], ["Relocate?", prettify(d.goals.willing_to_relocate || "—")]])}
    <div class="card"><h2>Saved careers</h2>
      ${saved.length ? `<div class="chips">${saved.map((c) => `<button class="chip" data-route="career" data-cid="${c.id}">${escapeHtml(c.name)}</button>`).join("")}</div>`
        : "<p class='muted'>Nothing saved yet — tap ☆ Save on any career you like.</p>"}</div>
    <div class="card"><h2>Assessment history</h2>
      ${metaGrid([["First assessment", fmtDate(d.metadata.created_at)], ["Last updated", fmtDate(d.metadata.updated_at)],
        ["Last Career Pulse", d.metadata.last_pulse_at ? fmtDate(d.metadata.last_pulse_at) : "Not yet"],
        ["Profile verified", prettify(d.metadata.validation_status)],
        ["Extraction", d.metadata.extraction_provider === "ai" ? "AI-powered" : "Deterministic"]])}
      <div class="action-bar"><button class="btn secondary" data-route="wizard">Retake assessment</button>
        <button class="btn secondary" data-route="pulse">Career Pulse</button></div></div>
    ${growth}
    <div class="card"><h2>Account</h2>
      <div class="action-bar"><button class="btn ghost" id="signout">Start fresh (new student)</button></div></div>`;
  view.querySelector("#signout").addEventListener("click", () => {
    if (confirm("Start over with a fresh profile? Your current local data will be cleared.")) { store.reset(); setRoute("dashboard"); }
  });
}

function growthFromEvidence(d) {
  const items = [
    ["Assessment completed", d.assessment.completion >= 0.8],
    ["Evidence collected", Object.keys(d.extracted_features).length >= 8],
    ["Academic data", d.academic.length > 0],
    ["Career goals set", !!(d.goals.dream_career || d.goals.preferred_work_style || d.goals.entrepreneurship_interest)],
    ["Profile verified", ["yes", "partially"].includes(d.metadata.validation_status)],
  ];
  const done = items.filter(([, ok]) => ok).length;
  const percent = Math.round((done / items.length) * 100);
  return `<div class="card"><h2>Profile completeness</h2>
    <div class="progress"><div style="width:${percent}%"></div></div>
    <p class="muted">${percent}% complete</p>
    <ul class="growth-list">${items.map(([label, ok]) => `<li class="${ok ? "done" : "todo"}"><span class="tick">${ok ? "✓" : "○"}</span><span>${label}</span></li>`).join("")}</ul></div>`;
}

// ============================================================================
// EXPLORE CAREERS — the career encyclopedia
// ============================================================================
function careerCard(c) {
  const saved = store.isSaved(c.id);
  return `<div class="card clickable" data-route="career" data-cid="${c.id}">
    <div class="rec"><div><h3 style="margin:0 0 4px">${escapeHtml(c.name)}</h3>
      <p class="muted" style="margin:0 0 8px">${escapeHtml(c.student_summary)}</p>
      <div class="row">${c.tags.map((t) => pill(t)).join("")}</div></div></div>
    ${metaGrid([["Salary", `₹${c.salary_entry_lpa}–${c.salary_senior_lpa} LPA`],
                ["Demand", Math.round(c.future_demand * 100) + "%"],
                ["Remote", Math.round(c.remote_work * 100) + "%"],
                ["Difficulty", "★".repeat(c.difficulty)]])}
    <div class="action-bar">
      <button class="btn secondary" data-route="career" data-cid="${c.id}">Explore</button>
      ${sid() ? `<button class="btn ghost" data-route="compare" data-a="${c.id}">Compare</button>` : ""}
      <button class="btn ghost" data-save="${c.id}" data-name="${escapeHtml(c.name)}">${saved ? "★ Saved" : "☆ Save"}</button>
    </div></div>`;
}

async function renderExplore() {
  skeleton(6);
  const env = await apiGet("/careers/industries");
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const industries = env.data.map((i) => `
    <div class="card clickable industry-card" data-route="industry" data-cid="${i.id}">
      <div class="icon">${i.icon}</div><h3>${escapeHtml(i.name)}</h3>
      <p class="muted">${escapeHtml(i.description)}</p>
      <div class="row">${pill(`${i.career_count} careers`)}
      ${(i.trending_careers || []).slice(0, 2).map((t) => pill("🔥 " + prettify(t.replace(/-/g, " ")))).join("")}</div>
    </div>`).join("");
  view.innerHTML = `
    <div class="card hero stack"><h1>🧭 Explore Careers</h1>
      <p>An interactive career encyclopedia — ${env.data.reduce((n, i) => n + i.career_count, 0)} career
      paths across ${env.data.length} industries.</p>
      <form id="explore-search" class="chat-form"><input id="explore-q" type="text"
        placeholder="Search career, industry, skill, subject, country…" aria-label="Search careers" />
        <button class="btn" type="submit">Search</button></form>
      <div class="row" id="quick-filters">
        ${["remote", "ai_safe", "government", "entrepreneurship", "creativity", "no_programming", "outdoor", "people"]
          .map((f) => `<button class="chip" type="button" data-filter="${f}">${prettify(f)}</button>`).join("")}
      </div></div>
    <div class="grid grid-3">${industries}</div>
    ${interestButtons()}`;
  view.querySelector("#explore-search").addEventListener("submit", (e) => {
    e.preventDefault(); renderCareerSearch(view.querySelector("#explore-q").value, {});
  });
  view.querySelectorAll("[data-filter]").forEach((b) =>
    b.addEventListener("click", () => renderCareerSearch("", { [b.dataset.filter]: true })));
}

async function renderCareerSearch(q, filters) {
  skeleton(5);
  const params = new URLSearchParams({ q: q || "", ...Object.fromEntries(Object.entries(filters || {}).map(([k, v]) => [k, String(v)])) });
  const env = await apiGet(`/careers/search?${params}`);
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const label = q ? `results for “${escapeHtml(q)}”` : `filter: ${Object.keys(filters).map(prettify).join(", ") || "all"}`;
  view.innerHTML = `<div class="card stack"><h1>Career search</h1>
    <form id="explore-search" class="chat-form"><input id="explore-q" type="text" value="${escapeHtml(q || "")}"
      placeholder="Search career, industry, skill, subject, country…" /><button class="btn" type="submit">Search</button></form>
    <p class="muted">${env.data.length} ${label}</p>
    <div><button class="btn secondary" data-route="explore">← All industries</button></div></div>
    <div class="grid grid-2">${env.data.map(careerCard).join("") ||
      `<div class='card'><p class='muted'>No careers match — try fewer filters.</p>
       <div class="action-bar"><button class="btn" data-route="explore">Explore industries</button>
       <button class="btn secondary" data-route="coach">Ask the AI Coach</button></div></div>`}</div>`;
  view.querySelector("#explore-search").addEventListener("submit", (e) => {
    e.preventDefault(); renderCareerSearch(view.querySelector("#explore-q").value, {});
  });
}

async function renderIndustry(iid) {
  skeleton(6);
  const env = await apiGet(`/careers/industries/${iid}`);
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const d = env.data;
  view.innerHTML = `
    <div class="card hero stack"><h1>${d.icon} ${escapeHtml(d.name)}</h1>
      <p>${escapeHtml(d.description)}</p><p style="opacity:.85">${escapeHtml(d.future_note)}</p>
      <div><button class="btn secondary" data-route="explore">← All industries</button></div></div>
    <div class="grid grid-2">${d.careers.map(careerCard).join("")}</div>`;
}

async function renderCareerProfile(cid) {
  skeleton(8);
  const env = await apiGet(`/careers/${cid}`);
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const p = env.data;
  store.addRecent(p.id, p.name);
  const saved = store.isSaved(p.id);
  const section = (title, items) => `<div class="card"><h2>${title}</h2>${list(items)}</div>`;
  const pills = (items, cls = "") => `<div class="row">${items.map((i) => pill(i, cls)).join("")}</div>`;
  view.innerHTML = `
    <div class="card hero stack"><h1>${escapeHtml(p.name)}</h1>
      <p>${escapeHtml(p.overview)}</p>
      <div class="row">${pill(p.industry_name)}${pill(p.career_family)}${p.tags.map((t) => pill(t)).join("")}</div>
      <div class="action-bar">
        ${sid() ? `<button class="btn" data-route="detail" data-cid="${p.id}">My personal fit</button>` : ""}
        <button class="btn secondary" data-save="${p.id}" data-name="${escapeHtml(p.name)}">${saved ? "★ Saved" : "☆ Save career"}</button>
        ${sid() ? `<button class="btn secondary" data-route="compare" data-a="${p.id}">Compare</button>` : ""}
      </div></div>
    ${metaCard("Snapshot", [["Salary (India)", p.salary_entry_lpa === 0 ? `Variable — up to ₹${p.salary_senior_lpa} LPA` : `₹${p.salary_entry_lpa}–${p.salary_senior_lpa} LPA`],
      ["Future demand", Math.round(p.future_demand * 100) + "%"], ["Remote work", Math.round(p.remote_work * 100) + "%"],
      ["Automation risk", Math.round(p.automation_risk * 100) + "%"], ["Difficulty", "★".repeat(p.difficulty)],
      ["Competition", "★".repeat(p.competition_level)]])}
    <div class="grid grid-2">
      ${section("Who is this for", p.who_is_this_for)}
      ${section("Who should think twice", p.who_should_avoid)}
    </div>
    ${section("What professionals actually do", p.daily_responsibilities)}
    <div class="grid grid-2">
      <div class="card"><h2>Work environment</h2><p class="muted">${escapeHtml(p.work_environment)}</p>
        <h2 style="margin-top:12px">Problem-solving style</h2><p class="muted">${escapeHtml(p.problem_solving_style)}</p></div>
      <div class="card"><h2>AI impact</h2><p class="muted">${escapeHtml(p.ai_impact)}</p>
        <h2 style="margin-top:12px">Scope</h2><p class="muted">${escapeHtml(p.scope)}</p></div>
    </div>
    <div class="grid grid-2">
      ${section("School subjects", p.school_subjects)}
      ${section("College degrees", p.college_degrees.concat(p.alternative_paths))}
    </div>
    <div class="card"><h2>Skills</h2>
      <p style="margin:.4rem 0"><strong>Core</strong></p>${pills(p.core_skills, "tag-strength")}
      <p style="margin:.6rem 0 .2rem"><strong>Technical</strong></p>${pills(p.technical_skills)}
      <p style="margin:.6rem 0 .2rem"><strong>Soft</strong></p>${pills(p.soft_skills)}
      <p style="margin:.6rem 0 .2rem"><strong>Future</strong></p>${pills(p.future_skills)}</div>
    <div class="card"><h2>Career progression</h2>${list(p.career_progression.map(([t, y]) => `${t} (${y})`))}</div>
    <div class="grid grid-2">
      ${section("Advantages", p.advantages)}
      ${section("Challenges", p.challenges)}
    </div>
    ${section("Common misconceptions", p.misconceptions)}
    <div class="grid grid-2">
      ${section("Portfolio & projects", p.portfolio_ideas.concat(p.projects))}
      ${section("Certifications & internships", p.certifications.concat(p.internships))}
    </div>
    <div class="grid grid-2">
      ${section("Universities", p.universities)}
      ${section("Scholarships", p.scholarships)}
    </div>
    <div class="card"><h2>India opportunities</h2>
      <p><strong>Hiring cities:</strong> ${p.major_hiring_cities.map((c) => pill(c)).join("")}</p>
      <p class="muted">${escapeHtml(p.smaller_city_scope)} ${escapeHtml(p.rural_scope)}</p>
      <p class="muted">${escapeHtml(p.home_state_note)}</p></div>
    <div class="card"><h2>Global opportunities</h2>
      <p><strong>Top countries:</strong> ${p.top_countries.map((c) => pill(c)).join("")}</p>
      <p class="muted">Languages: ${p.language_requirements.join("; ")} · Visa difficulty: ${p.visa_difficulty}</p></div>
    ${section("Learning resources", p.books.concat(p.courses, p.youtube, p.communities))}
    <div class="card"><h2>FAQs</h2>${p.faqs.map(([q, a]) =>
      `<details class="expand"><summary>${escapeHtml(q)}</summary><p class="muted">${escapeHtml(a)}</p></details>`).join("")}</div>
    <div class="card"><h2>Explore similar careers</h2>
      <div class="grid grid-2">${p.related_profiles.map(careerCard).join("")}</div>
      ${section("Transition paths", p.transition_paths)}</div>
    <div class="action-bar">
      <button class="btn secondary" data-route="industry" data-cid="${p.industry}">← ${escapeHtml(p.industry_name)}</button>
      <button class="btn secondary" data-route="explore">All industries</button>
    </div>`;
  window.scrollTo(0, 0);
}

// ============================================================================
// ROUTER
// ============================================================================
const ROUTES = {
  dashboard: renderDashboard,
  explore: renderExplore,
  assessment: renderAssessment,
  wizard: renderWizard,
  validation: () => renderValidation(null),
  pulse: renderPulse,
  matches: renderMatches,
  experiments: renderExperiments,
  reflect: (p) => renderReflect(p.xid),
  coach: (p) => renderCoach(p),
  profile: renderProfile,
  compare: (p) => renderCompare(p),
  detail: (p) => renderDetail(p.cid),
  roadmap: (p) => renderRoadmap(p.cid),
  skillgap: (p) => renderSkillGap(p.cid),
  industry: (p) => renderIndustry(p.cid),
  career: (p) => renderCareerProfile(p.cid),
  search: () => renderCareerSearch("", {}),
};
const NAV_HIGHLIGHT = { wizard: "assessment", validation: "assessment", pulse: "assessment",
  detail: "matches", roadmap: "matches", skillgap: "matches", compare: "matches",
  experiments: "matches", reflect: "matches",
  industry: "explore", career: "explore", search: "explore" };

function setRoute(name, params = {}) {
  const render = ROUTES[name] || renderDashboard;
  const highlight = NAV_HIGHLIGHT[name] || name;
  document.querySelectorAll(".nav-btn").forEach((b) => b.setAttribute("aria-current", b.dataset.route === highlight ? "page" : "false"));
  document.getElementById("main").focus();
  render(params);
}

document.addEventListener("click", async (e) => {
  const accept = e.target.closest("[data-xaccept]");
  if (accept) {
    const d = await experimentAction(`/students/${sid()}/experiments/${accept.dataset.xaccept}/accept`,
      "It's on! Come back when you've tried it.");
    if (d) setRoute("experiments");
    return;
  }
  const skip = e.target.closest("[data-xskip]");
  if (skip) {
    const d = await experimentAction(`/students/${sid()}/experiments/${skip.dataset.xskip}/skip`,
      "Swapped — here's a different way to test it.");
    if (d) setRoute("experiments");
    return;
  }
  const save = e.target.closest("[data-save]");
  if (save) {
    e.stopPropagation(); e.preventDefault();
    const on = store.toggleSaved(save.dataset.save, save.dataset.name);
    save.textContent = on ? "★ Saved" : "☆ Save";
    toast(on ? "Saved to your profile." : "Removed from saved careers.");
    return;
  }
  const interest = e.target.closest("[data-interest]");
  if (interest) {
    const f = JSON.parse(interest.dataset.interest);
    if (f.q) renderCareerSearch(f.q, {}); else renderCareerSearch("", f);
    return;
  }
  const t = e.target.closest("[data-route]");
  if (t && t.tagName !== "A") {
    e.preventDefault();
    setRoute(t.dataset.route, { cid: t.dataset.cid, a: t.dataset.a, b: t.dataset.b, prompt: t.dataset.prompt, xid: t.dataset.xid });
  }
});

// ---- theme ------------------------------------------------------------------
const themeBtn = document.getElementById("theme-toggle");
const themes = ["system", "light", "dark"];
const applyTheme = (t) => { document.documentElement.setAttribute("data-theme", t); localStorage.setItem("dm.theme", t); };
applyTheme(localStorage.getItem("dm.theme") || "system");
themeBtn.addEventListener("click", () => { const cur = document.documentElement.getAttribute("data-theme"); applyTheme(themes[(themes.indexOf(cur) + 1) % themes.length]); });

setRoute("dashboard");
