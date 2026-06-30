// Detective Monkey — AI Career Mentor SPA (Phase 2).
// Presentation + flow only; all reasoning lives in the backend Intelligence Engine.

const API = "/api/v1";
const view = document.getElementById("view");
const toastEl = document.getElementById("toast");

// ---- store --------------------------------------------------------------
const store = {
  get studentId() { return localStorage.getItem("dm.studentId"); },
  get name() { return localStorage.getItem("dm.name") || ""; },
  setStudent(name, id) { localStorage.setItem("dm.name", name); localStorage.setItem("dm.studentId", id); },
};
function newStudentId(name) {
  const slug = (name || "student").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24) || "student";
  return `${slug}-${Math.random().toString(36).slice(2, 6)}`;
}

// ---- api ----------------------------------------------------------------
async function apiGet(p) { return (await fetch(API + p)).json(); }
async function apiPost(p, b) {
  return (await fetch(API + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) })).json();
}
const sid = () => store.studentId;
const envError = (e) => (e && e.errors && e.errors.length ? e.errors[0].message : "Something went wrong.");
const notFound = (e) => e && e.errors && e.errors[0] && e.errors[0].code === "NOT_FOUND";

// ---- helpers ------------------------------------------------------------
let toastTimer;
function toast(m) { toastEl.textContent = m; toastEl.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => (toastEl.hidden = true), 2800); }
function el(h) { const t = document.createElement("template"); t.innerHTML = h.trim(); return t.content.firstElementChild; }
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function prettify(s) { return String(s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function pill(t, cls = "") { return `<span class="pill ${cls}">${escapeHtml(t)}</span>`; }
function list(items, cls = "") { return `<ul class="${cls}" style="margin:6px 0 0 18px">${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`; }
function bar(label, value) { const p = Math.max(0, Math.min(100, value)); return `<div class="bar-row"><div class="bar-label"><span>${escapeHtml(label)}</span><span class="muted">${Math.round(p)}</span></div><div class="bar-track"><div class="bar-fill" style="width:${p}%"></div></div></div>`; }
function skeleton(n = 4) { view.innerHTML = `<div class="card stack">${Array.from({ length: n }).map(() => `<div class="skeleton" style="width:${55 + Math.random() * 40}%"></div>`).join("")}</div>`; }
function errorCard(m) { return `<div class="card stack"><h1>Something went wrong</h1><p class="muted">${escapeHtml(m)}</p><div><button class="btn secondary" data-route="dashboard">Home</button></div></div>`; }
function emptyCard(t, b, route, cta) { return `<div class="card stack"><h1>${t}</h1><p class="muted">${b}</p><div><button class="btn" data-route="${route}">${cta}</button></div></div>`; }

// ---- onboarding ---------------------------------------------------------
function renderOnboarding() {
  view.innerHTML = `<div class="card hero stack"><h1>Meet your AI Career Mentor</h1>
    <p>Answer a short assessment and I'll build an evidence-based picture of your strengths,
       recommend careers that fit you, and guide your next steps — personally.</p></div>
    <div class="card stack"><label for="name">What's your name?</label>
      <input id="name" type="text" placeholder="e.g. Sandeepan" />
      <div><button class="btn" id="start">Start my assessment →</button></div></div>`;
  const input = view.querySelector("#name"); input.focus();
  view.querySelector("#start").addEventListener("click", () => {
    const name = input.value.trim();
    if (!name) { toast("Please enter your name."); return; }
    store.setStudent(name, newStudentId(name)); setRoute("assessment");
  });
}

// ---- dashboard (Epic 1) -------------------------------------------------
async function renderDashboard() {
  if (!sid()) return renderOnboarding();
  skeleton(6);
  const env = await apiGet(`/students/${sid()}/dashboard`);
  if (!env.success) {
    if (notFound(env)) return void (view.innerHTML = emptyCard("Let's build your profile", "Take the assessment to unlock your AI career dashboard.", "assessment", "Take the assessment"));
    return void (view.innerHTML = errorCard(envError(env)));
  }
  const d = env.data;
  const ring = `<div class="ring" style="--p:${d.readiness.score}"><span>${d.readiness.score}%</span></div>`;
  const strengths = d.strengths.map((s) => `<div class="tile"><div class="label">${escapeHtml(s.title)}</div>
    ${bar("confidence", s.confidence)}<p class="muted" style="font-size:.85rem">${escapeHtml(s.explanation)}</p></div>`).join("");
  view.innerHTML = `
    ${d.greeting ? `<div class="card hero"><p style="margin:0">${escapeHtml(d.greeting)}</p></div>` : ""}
    <div class="card hero stack"><h1>Hi ${escapeHtml(store.name)} — here's your career intelligence</h1>
      <p>${escapeHtml(d.ai_summary)}</p></div>

    <div class="grid grid-2">
      <div class="card"><h2>Career Readiness</h2>
        <div class="readiness-ring">${ring}
          <div><strong>${escapeHtml(d.readiness.level)}</strong>
            <p class="muted" style="margin:4px 0">${escapeHtml(d.readiness.explanation)}</p></div></div>
        <details class="expand"><summary>What changes this score</summary>
          <p style="margin:.4rem 0"><strong>Increases ↑</strong></p>${list(d.readiness.increases)}
          <p style="margin:.4rem 0"><strong>Decreases ↓</strong></p>${list(d.readiness.decreases)}</details>
      </div>
      <div class="card"><h2>Learning Style</h2>
        <p class="big" style="font-size:1.5rem;color:var(--color-primary);font-weight:800">${prettify(d.learning_style.style)}</p>
        <p class="muted">${escapeHtml(d.learning_style.explanation)}</p></div>
    </div>

    <div class="card"><h2>Top Strengths</h2><div class="grid grid-3">${strengths}</div></div>

    <div class="grid grid-2">
      <div class="card"><h2>🎯 Biggest Opportunity</h2>
        <p><strong>${escapeHtml(d.opportunity.title)}</strong></p>
        <p class="muted">${escapeHtml(d.opportunity.detail)}</p>
        <div class="row">${pill(`+${d.opportunity.employability_gain}% employability`)}${pill(`+${d.opportunity.extra_careers} careers`)}</div></div>
      <div class="card"><h2>✅ Today's Recommendation</h2>
        <p><strong>${escapeHtml(d.todays_action.title)}</strong></p>
        <p class="muted">${escapeHtml(d.todays_action.detail)}</p>${pill(`Impact: ${d.todays_action.impact}`)}</div>
    </div>

    <div class="card stack"><h2>Continue</h2><div class="action-bar">
      <button class="btn" data-route="recommendations">View recommendations</button>
      <button class="btn secondary" data-route="coach">Ask your mentor</button>
      <a class="btn secondary" href="${API}/students/${sid()}/report" target="_blank" rel="noopener">Download AI report</a>
    </div></div>`;
}

// ---- assessment (Epic flow) --------------------------------------------
async function renderAssessment() {
  if (!sid()) return renderOnboarding();
  skeleton(5);
  const env = await apiGet("/assessments/default");
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const questions = env.data.sections.flatMap((s) => s.questions);
  const answers = {};
  function draw() {
    const answered = Object.keys(answers).length;
    view.innerHTML = `<div class="card"><h1>Career Compass</h1>
      <p class="muted">Rate each statement (1 = strongly disagree, 5 = strongly agree).</p>
      <div class="progress"><div style="width:${(answered / questions.length) * 100}%"></div></div>
      <p class="muted">${answered} / ${questions.length} answered</p></div>
      <div class="card" id="qs"></div>
      <div class="row"><button class="btn" id="submit" ${answered < questions.length ? "disabled" : ""}>Analyze my results →</button></div>`;
    const qs = view.querySelector("#qs");
    questions.forEach((q) => {
      const row = el(`<div class="question"><p>${escapeHtml(q.prompt)}</p><div class="likert" role="group" aria-label="${escapeHtml(q.prompt)}"></div></div>`);
      const g = row.querySelector(".likert");
      for (let v = 1; v <= 5; v++) { const b = el(`<button type="button" aria-pressed="${answers[q.id] === v}">${v}</button>`); b.addEventListener("click", () => { answers[q.id] = v; draw(); }); g.appendChild(b); }
      qs.appendChild(row);
    });
    const sub = view.querySelector("#submit");
    if (sub) sub.addEventListener("click", async () => {
      skeleton(4);
      const payload = { answers: Object.entries(answers).map(([id, v]) => ({ question_id: id, value: v, duration_ms: 1500 })) };
      const r = await apiPost(`/students/${sid()}/assessment`, payload);
      if (!r.success) { view.innerHTML = errorCard(envError(r)); return; }
      toast("Your AI profile is ready!");
      setRoute("dashboard");
    });
  }
  draw();
}

// ---- recommendations (Epic 2) ------------------------------------------
function metaGrid(pairs) {
  return `<div class="meta-grid">${pairs.map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${escapeHtml(v)}</div></div>`).join("")}</div>`;
}
function premiumCard(c) {
  const skills = c.skill_gaps.map((s) => prettify(s));
  return el(`<div class="card">
    <div class="rec"><div><h2 style="margin:0">${escapeHtml(c.name)}</h2>
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
      ${c.alternatives.length ? `<p style="margin:.6rem 0 .2rem"><strong>Alternatives</strong></p><div class="row">${c.alternatives.map((a) => pill(a)).join("")}</div>` : ""}
    </details>
    <div class="action-bar">
      <button class="btn" data-route="detail" data-cid="${c.career_id}">Explore career</button>
      <button class="btn secondary" data-route="roadmap" data-cid="${c.career_id}">Roadmap</button>
      <button class="btn secondary" data-route="skillgap" data-cid="${c.career_id}">Skill gap</button>
    </div></div>`);
}
async function renderRecommendations() {
  if (!sid()) return renderOnboarding();
  skeleton(5);
  const env = await apiPost(`/students/${sid()}/recommendations`, {});
  if (!env.success) {
    if (notFound(env)) return void (view.innerHTML = emptyCard("Build your profile first", "Recommendations need an assessment.", "assessment", "Take the assessment"));
    return void (view.innerHTML = errorCard(envError(env)));
  }
  const cards = env.data.cards || [];
  view.innerHTML = `<div class="card stack"><h1>Your career matches</h1>
    <p class="muted">Each match explains <strong>why it fits you</strong>, the evidence used, and what's next.</p>
    <div class="action-bar"><button class="btn secondary" data-route="compare">Compare careers</button></div></div>
    <div id="recs"></div>`;
  const c = view.querySelector("#recs");
  if (!cards.length) { c.innerHTML = "<div class='card muted'>No matches yet.</div>"; return; }
  cards.forEach((m) => c.appendChild(premiumCard(m)));
}

// ---- career detail (Epic 3) --------------------------------------------
async function renderDetail(cid) {
  if (!sid()) return renderOnboarding();
  skeleton(6);
  const env = await apiGet(`/students/${sid()}/careers/${cid}`);
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
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
    <div class="card"><h2>Related careers</h2><div class="row">${d.related_careers.map((r) => pill(r)).join("")}</div></div>
    ${roadmapCard(d.roadmap)}
    <div class="action-bar"><button class="btn secondary" data-route="skillgap" data-cid="${cid}">See skill gap</button>
      <button class="btn secondary" data-route="recommendations">← Back to matches</button></div>`;
}
function metaCard(title, pairs) { return `<div class="card"><h2>${title}</h2>${metaGrid(pairs)}</div>`; }

// ---- roadmap (Epic 6) ---------------------------------------------------
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

// ---- skill gap (Epic 7) -------------------------------------------------
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
    ${bar("Projected after learning", g.projected_compatibility)}
    <p class="muted">Learning these skills raises your compatibility from
      <strong>${g.current_compatibility}%</strong> to <strong>${g.projected_compatibility}%</strong>.</p></div>
    <div class="card"><h2>You already bring</h2><div class="row">${g.strengths.map((s) => pill(s, "tag-strength")).join("") || "<span class='muted'>—</span>"}</div></div>
    <div class="card"><h2>Skills to develop</h2>${missing || "<p class='muted'>You're ready for this role!</p>"}</div>
    <div class="action-bar"><button class="btn" data-route="roadmap" data-cid="${cid}">See learning roadmap</button></div>`;
}

// ---- comparison (Epic 8) ------------------------------------------------
async function renderCompare() {
  if (!sid()) return renderOnboarding();
  skeleton(4);
  const env = await apiPost(`/students/${sid()}/recommendations`, {});
  if (!env.success) return void (view.innerHTML = errorCard(envError(env)));
  const cards = env.data.cards || [];
  const opts = cards.map((c) => `<option value="${c.career_id}">${escapeHtml(c.name)}</option>`).join("");
  view.innerHTML = `<div class="card stack"><h1>Compare careers</h1>
    <div class="row"><select id="a">${opts}</select><span>vs</span><select id="b">${opts}</select>
      <button class="btn" id="go">Compare</button></div></div><div id="out"></div>`;
  if (cards[1]) view.querySelector("#b").value = cards[1].career_id;
  view.querySelector("#go").addEventListener("click", async () => {
    const a = view.querySelector("#a").value, b = view.querySelector("#b").value;
    if (a === b) { toast("Pick two different careers."); return; }
    const r = await apiGet(`/students/${sid()}/compare?a=${a}&b=${b}`);
    const out = view.querySelector("#out");
    if (!r.success) { out.innerHTML = errorCard(envError(r)); return; }
    const d = r.data;
    const rows = d.rows.map((row) => `<tr><td>${escapeHtml(row.dimension)}</td>
      <td class="${row.winner === "a" ? "win" : ""}">${escapeHtml(row.a)}</td>
      <td class="${row.winner === "b" ? "win" : ""}">${escapeHtml(row.b)}</td></tr>`).join("");
    out.innerHTML = `<div class="card"><table class="cmp"><thead><tr><th></th><th>${escapeHtml(d.career_a)}</th><th>${escapeHtml(d.career_b)}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="card hero"><h2 style="color:#fff">AI recommendation</h2><p style="margin:0">${escapeHtml(d.recommendation)}</p></div>`;
  });
  view.querySelector("#go").click();
}

// ---- coach (Epics 4 & 5) ------------------------------------------------
async function renderCoach() {
  if (!sid()) return renderOnboarding();
  view.innerHTML = `<div class="card"><h1>AI Career Mentor</h1>
    <p class="muted">I know your profile, strengths and matches — ask me anything about your next steps.</p></div>
    <div class="card"><div class="chat-log" id="log"></div>
      <div class="chips" id="chips"></div>
      <form class="chat-form" id="chat"><input id="msg" type="text" placeholder="Ask your mentor…" aria-label="Message" /><button class="btn" type="submit">Send</button></form></div>`;
  const log = view.querySelector("#log");
  const chips = view.querySelector("#chips");
  const add = (t, who) => { log.appendChild(el(`<div class="msg ${who}">${escapeHtml(t)}</div>`)); log.scrollTop = log.scrollHeight; };
  add("Welcome back! What would you like to work on today?", "bot");

  async function send(message) {
    if (!message.trim()) return;
    add(message, "user");
    const r = await apiPost("/conversations", { message, student_id: sid() });
    const data = r.success ? r.data : null;
    add(data ? data.response : envError(r), "bot");
    if (data && data.suggestions) renderChips(data.suggestions);
  }
  function renderChips(qs) {
    chips.innerHTML = "";
    (qs || []).forEach((q) => { const b = el(`<button class="chip" type="button">${escapeHtml(q)}</button>`); b.addEventListener("click", () => send(q)); chips.appendChild(b); });
  }
  // Seed dynamic suggestions from the dashboard.
  const dash = await apiGet(`/students/${sid()}/dashboard`);
  renderChips(dash.success ? dash.data.suggested_questions : ["What should I study next?", "Build me a roadmap", "Compare my careers"]);

  view.querySelector("#chat").addEventListener("submit", (e) => { e.preventDefault(); const i = view.querySelector("#msg"); const m = i.value; i.value = ""; i.focus(); send(m); });
}

// ---- router -------------------------------------------------------------
const ROUTES = {
  dashboard: renderDashboard, assessment: renderAssessment, recommendations: renderRecommendations,
  coach: renderCoach, compare: renderCompare,
  detail: (p) => renderDetail(p.cid), roadmap: (p) => renderRoadmap(p.cid), skillgap: (p) => renderSkillGap(p.cid),
};
const NAV = ["dashboard", "assessment", "recommendations", "coach"];
function setRoute(name, params = {}) {
  const render = ROUTES[name] || renderDashboard;
  document.querySelectorAll(".nav-btn").forEach((b) => b.setAttribute("aria-current", b.dataset.route === name ? "page" : "false"));
  document.getElementById("main").focus();
  render(params);
}
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-route]");
  if (t && t.tagName !== "A") { e.preventDefault(); setRoute(t.dataset.route, { cid: t.dataset.cid }); }
});

// ---- theme --------------------------------------------------------------
const themeBtn = document.getElementById("theme-toggle");
const themes = ["system", "light", "dark"];
const applyTheme = (t) => { document.documentElement.setAttribute("data-theme", t); localStorage.setItem("dm.theme", t); };
applyTheme(localStorage.getItem("dm.theme") || "system");
themeBtn.addEventListener("click", () => { const cur = document.documentElement.getAttribute("data-theme"); applyTheme(themes[(themes.indexOf(cur) + 1) % themes.length]); });

setRoute("dashboard");
