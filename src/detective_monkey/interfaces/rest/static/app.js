// Detective Monkey SPA (50_UI_SYSTEM.md, 52_USER_FLOWS.md).
// Presentation + flow orchestration only — all business logic lives in the backend.

const API = "/api/v1";
const view = document.getElementById("view");
const toastEl = document.getElementById("toast");

// Friendly labels for the seeded careers (display only).
const CAREER_NAMES = {
  c_ds: "Data Scientist", c_swe: "Software Engineer", c_ux: "UX Designer",
  c_pm: "Product Manager", c_rs: "Research Scientist",
};
const careerName = (id) => CAREER_NAMES[id] || id;

// ---- store (server/app/ui state owners, 50 §13) -------------------------
const store = {
  get studentId() { return localStorage.getItem("dm.studentId"); },
  get name() { return localStorage.getItem("dm.name") || ""; },
  setStudent(name, id) {
    localStorage.setItem("dm.name", name);
    localStorage.setItem("dm.studentId", id);
  },
};

function newStudentId(name) {
  const slug = (name || "student").toLowerCase().replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "").slice(0, 24) || "student";
  return `${slug}-${Math.random().toString(36).slice(2, 6)}`; // no underscores
}

// ---- api client ---------------------------------------------------------
async function apiGet(path) {
  const res = await fetch(API + path);
  return res.json();
}
async function apiPost(path, body) {
  const res = await fetch(API + path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}
function envError(env) {
  return env && env.errors && env.errors.length ? env.errors[0].message : "Something went wrong.";
}

// ---- ui helpers ---------------------------------------------------------
let toastTimer;
function toast(msg) {
  toastEl.textContent = msg; toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3000);
}
function el(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }
function bar(label, value) {
  const pct = Math.max(0, Math.min(100, value));
  return `<div class="bar-row"><div class="bar-label"><span>${label}</span><span class="muted">${pct.toFixed(0)}</span></div>
    <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div></div>`;
}
function skeleton(lines = 3) {
  view.innerHTML = `<div class="card stack">${Array.from({ length: lines })
    .map(() => `<div class="skeleton" style="width:${60 + Math.random() * 40}%"></div>`).join("")}</div>`;
}

// ---- views --------------------------------------------------------------
function renderDashboard() {
  if (!store.studentId) return renderOnboarding();
  view.innerHTML = `
    <div class="card stack">
      <h1>Welcome back, ${store.name || "explorer"} 👋</h1>
      <p class="muted">Continue your journey toward a confident career decision.</p>
      <div class="row">
        <button class="btn" data-route="assessment">Take the assessment</button>
        <button class="btn secondary" data-route="recommendations">View recommendations</button>
        <button class="btn secondary" data-route="coach">Ask the AI coach</button>
      </div>
    </div>
    <div class="card">
      <h2>How it works</h2>
      <p class="muted">Answer a short assessment → we build an evidence-based profile →
      we recommend careers with transparent explanations → ask the coach anything.
      We offer guidance, never predictions.</p>
    </div>`;
}

function renderOnboarding() {
  view.innerHTML = `
    <div class="card stack">
      <h1>Let's get started</h1>
      <p class="muted">Tell us your name to begin. No account needed for the demo.</p>
      <div><label for="name">Your name</label>
        <input id="name" type="text" placeholder="e.g. Sandeepan" autocomplete="given-name" /></div>
      <div><button class="btn" id="start">Start assessment</button></div>
    </div>`;
  const input = view.querySelector("#name");
  input.focus();
  view.querySelector("#start").addEventListener("click", () => {
    const name = input.value.trim();
    if (!name) { toast("Please enter your name."); input.focus(); return; }
    store.setStudent(name, newStudentId(name));
    setRoute("assessment");
  });
}

async function renderAssessment() {
  if (!store.studentId) return renderOnboarding();
  skeleton(5);
  const env = await apiGet("/assessments/default");
  if (!env.success) { view.innerHTML = errorCard(envError(env)); return; }
  const questions = env.data.sections.flatMap((s) => s.questions);
  const answers = {};

  function draw() {
    const answered = Object.keys(answers).length;
    const pct = (answered / questions.length) * 100;
    view.innerHTML = `
      <div class="card">
        <h1>Career Compass</h1>
        <p class="muted">Rate how much each statement sounds like you (1 = strongly disagree, 5 = strongly agree).</p>
        <div class="progress" role="progressbar" aria-valuenow="${answered}" aria-valuemin="0" aria-valuemax="${questions.length}">
          <div style="width:${pct}%"></div></div>
        <p class="muted">${answered} / ${questions.length} answered</p>
      </div>
      <div class="card" id="qs"></div>
      <div class="row"><button class="btn" id="submit" ${answered < questions.length ? "disabled" : ""}>See my results</button></div>`;
    const qs = view.querySelector("#qs");
    questions.forEach((q) => {
      const row = el(`<div class="question"><p>${q.prompt}</p>
        <div class="likert" role="group" aria-label="${q.prompt}"></div></div>`);
      const group = row.querySelector(".likert");
      for (let v = 1; v <= 5; v++) {
        const b = el(`<button type="button" aria-pressed="${answers[q.id] === v}">${v}</button>`);
        b.addEventListener("click", () => { answers[q.id] = v; draw(); });
        group.appendChild(b);
      }
      qs.appendChild(row);
    });
    const submit = view.querySelector("#submit");
    if (submit) submit.addEventListener("click", () => submitAssessment(answers, questions.length));
  }
  draw();
}

async function submitAssessment(answers, total) {
  if (Object.keys(answers).length < total) { toast("Please answer every question."); return; }
  skeleton(4);
  const payload = { answers: Object.entries(answers).map(([qid, v]) => ({ question_id: qid, value: v, duration_ms: 1500 })) };
  const env = await apiPost(`/students/${store.studentId}/assessment`, payload);
  if (!env.success) { view.innerHTML = errorCard(envError(env)); return; }
  renderProfile(env.data);
}

async function renderProfile(profile) {
  if (!profile) {
    skeleton(4);
    const env = await apiGet(`/students/${store.studentId}/profile`);
    if (!env.success) {
      view.innerHTML = emptyCard("No profile yet", "Take the assessment to build your profile.", "assessment", "Take assessment");
      return;
    }
    profile = env.data;
  }
  const constructs = (profile.constructs || []).map(([n, v]) => bar(prettify(n), v)).join("");
  const domains = (profile.domains || []).map(([n, v]) => bar(prettify(n), v)).join("");
  view.innerHTML = `
    <div class="card stack">
      <h1>Your profile</h1>
      <p class="muted">Built from evidence in your assessment. Profile completeness:
        ${Math.round((profile.completeness || 0) * 100)}%.</p>
    </div>
    <div class="card"><h2>Strengths (constructs)</h2>${constructs || "<p class='muted'>No data.</p>"}</div>
    <div class="card"><h2>Ability domains</h2>${domains || "<p class='muted'>No data.</p>"}</div>
    <div class="row"><button class="btn" data-route="recommendations">See career recommendations</button></div>`;
}

async function renderRecommendations() {
  if (!store.studentId) return renderOnboarding();
  skeleton(4);
  // Ensure profile exists first.
  const prof = await apiGet(`/students/${store.studentId}/profile`);
  if (!prof.success) {
    view.innerHTML = emptyCard("Build your profile first", "Recommendations need an assessment.", "assessment", "Take assessment");
    return;
  }
  const gen = await apiPost(`/students/${store.studentId}/recommendations`, {});
  if (!gen.success) { view.innerHTML = errorCard(envError(gen)); return; }
  const recs = gen.data.recommendations || [];
  view.innerHTML = `<div class="card stack"><h1>Your recommendations</h1>
    <p class="muted">Ranked by fit with evidence. Every recommendation is explainable —
    select “Why?” to see the reasoning.</p></div>
    <div id="recs"></div>`;
  const container = view.querySelector("#recs");
  if (!recs.length) { container.innerHTML = "<div class='card muted'>No matches yet.</div>"; return; }
  recs.forEach((r) => {
    const card = el(`<div class="card">
      <div class="rec">
        <div><h2 style="margin:0">${careerName(r.career_id)}</h2>
          <span class="pill">confidence ${(r.confidence * 100).toFixed(0)}%</span>
          <span class="pill">${r.skill_gap_count} skill gap(s)</span></div>
        <div style="text-align:center"><div class="score-badge">${r.overall_score.toFixed(0)}</div>
          <button class="btn secondary why" data-rec="${r.recommendation_id}">Why?</button></div>
      </div>
      <div class="explanation" hidden></div>
    </div>`);
    card.querySelector(".why").addEventListener("click", async (e) => {
      const box = card.querySelector(".explanation");
      if (!box.hidden) { box.hidden = true; return; }
      box.hidden = false; box.innerHTML = "<div class='skeleton' style='width:90%'></div>";
      const env = await apiGet(`/recommendations/${e.target.dataset.rec}/explanation`);
      box.innerHTML = env.success
        ? `<hr/><pre style="white-space:pre-wrap;font-family:inherit;margin:0">${escapeHtml(env.data.content)}</pre>`
        : `<p class="muted">${envError(env)}</p>`;
    });
    container.appendChild(card);
  });
}

function renderCoach() {
  if (!store.studentId) return renderOnboarding();
  view.innerHTML = `
    <div class="card"><h1>AI Career Coach</h1>
      <p class="muted">Ask about careers, recommendations or next steps. The coach answers
      from platform knowledge and your evidence — it never invents facts.</p></div>
    <div class="card">
      <div class="chat-log" id="log"></div>
      <form class="chat-form" id="chat">
        <input id="msg" type="text" placeholder="e.g. Tell me about data scientist" aria-label="Message" />
        <button class="btn" type="submit">Send</button>
      </form>
    </div>`;
  const log = view.querySelector("#log");
  const addMsg = (text, who) => { log.appendChild(el(`<div class="msg ${who}">${escapeHtml(text)}</div>`)); log.scrollTop = log.scrollHeight; };
  addMsg("Hi! What would you like to explore today?", "bot");
  view.querySelector("#chat").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = view.querySelector("#msg");
    const message = input.value.trim();
    if (!message) return;
    addMsg(message, "user"); input.value = ""; input.focus();
    const env = await apiPost("/conversations", { message, student_id: store.studentId });
    addMsg(env.success ? env.data.response : envError(env), "bot");
  });
}

// ---- small render utilities --------------------------------------------
function errorCard(msg) {
  return `<div class="card stack"><h1>Something went wrong</h1><p class="muted">${escapeHtml(msg)}</p>
    <div><button class="btn secondary" data-route="dashboard">Return home</button></div></div>`;
}
function emptyCard(title, body, route, cta) {
  return `<div class="card stack"><h1>${title}</h1><p class="muted">${body}</p>
    <div><button class="btn" data-route="${route}">${cta}</button></div></div>`;
}
function prettify(s) { return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

// ---- router -------------------------------------------------------------
const ROUTES = {
  dashboard: renderDashboard,
  assessment: renderAssessment,
  profile: () => renderProfile(null),
  recommendations: renderRecommendations,
  coach: renderCoach,
};
function setRoute(name) {
  const render = ROUTES[name] || renderDashboard;
  document.querySelectorAll(".nav-btn").forEach((b) =>
    b.setAttribute("aria-current", b.dataset.route === name ? "page" : "false"));
  document.getElementById("main").focus();
  render();
}
// Event delegation for any [data-route] button.
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-route]");
  if (t) setRoute(t.dataset.route);
});

// ---- theme (50 §12) -----------------------------------------------------
const themeBtn = document.getElementById("theme-toggle");
const themes = ["system", "light", "dark"];
function applyTheme(t) { document.documentElement.setAttribute("data-theme", t); localStorage.setItem("dm.theme", t); }
applyTheme(localStorage.getItem("dm.theme") || "system");
themeBtn.addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  applyTheme(themes[(themes.indexOf(cur) + 1) % themes.length]);
  toast(`Theme: ${document.documentElement.getAttribute("data-theme")}`);
});

// ---- boot ---------------------------------------------------------------
setRoute("dashboard");
