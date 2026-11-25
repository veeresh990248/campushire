/* CampusHire single-page app - vanilla JS, no build step. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const BRANCHES = ["CSE", "IT", "ECE", "EEE", "MECH", "CIVIL", "OTHER"];
const FLOW = ["applied", "shortlisted", "interview", "offered"];

let token = localStorage.getItem("ch_token");
let me = null; // { user, profile?, company? }

/* ------------------------------------------------------------ helpers */
async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (res.status === 401 && token) { signOutLocal(); }
  if (!res.ok) throw new Error(data.error || "Request failed (" + res.status + ")");
  return data;
}
function toast(msg, error = false) {
  const t = document.createElement("div");
  t.className = "toast" + (error ? " error" : ""); t.textContent = msg;
  $("#toasts").append(t); setTimeout(() => t.remove(), 3600);
}
function openModal(html) {
  closeModal();
  const o = document.createElement("div");
  o.className = "overlay"; o.innerHTML = `<div class="modal" role="dialog" aria-modal="true"><button class="close" aria-label="Close">&times;</button>${html}</div>`;
  o.addEventListener("mousedown", (e) => { if (e.target === o) closeModal(); });
  $(".close", o).onclick = closeModal;
  $("#modal-root").append(o);
  return o;
}
function closeModal() { $("#modal-root").innerHTML = ""; }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
const tone = (s) => (s >= 70 ? "hi" : s >= 45 ? "mid" : "lo");
const ring = (score, size = 60) => score == null
  ? `<div class="ring none" style="--s:${size}px;--p:0"><b>–</b></div>`
  : `<div class="ring ${tone(score)}" style="--s:${size}px;--p:${score}" title="${score}% match"><b>${score}</b></div>`;
const chips = (arr, cls = "") => (arr || []).map((s) => `<span class="chip ${cls}">${esc(s)}</span>`).join("");
const pill = (s) => `<span class="pill ${esc(s)}">${esc(s)}</span>`;
const money = (n) => (n ? `₹${n} LPA` : "Stipend n/a");
const fmtDate = (d) => new Date(d.length === 10 ? d + "T00:00:00" : d.replace(" ", "T") + "Z").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const daysLeft = (d) => Math.ceil((new Date(d + "T23:59:59") - new Date()) / 864e5);
const initials = (n) => n.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const setView = (html) => { $("#view").innerHTML = html; window.scrollTo(0, 0); };
const loading = () => setView(`<div class="empty">Loading…</div>`);
function signOutLocal() { token = null; me = null; localStorage.removeItem("ch_token"); location.hash = ""; renderAuth(); }
function btnBusy(btn, on, label) { btn.disabled = on; if (label) btn.textContent = on ? "Please wait…" : label; }

/* ------------------------------------------------------------ auth screen */
function renderAuth(mode = "login") {
  const reg = mode === "register";
  $("#app").innerHTML = `
  <div class="auth-wrap">
    <section class="hero">
      <div class="logo" style="color:#fff"><i style="background:#fff3"></i> CampusHire</div>
      <h1>Your campus placement season, matched by AI.</h1>
      <p>Students see how well they fit every opening before applying. Recruiters get applicants ranked by fit. Placement cells get live numbers.</p>
      <div class="feat">
        <div><b>AI resume matcher</b> – skill coverage, related-skill credit and text similarity, explained in plain language.</div>
        <div><b>Resume analyzer</b> – a score out of 100 with concrete fixes before you hit apply.</div>
        <div><b>Eligibility built in</b> – CGPA and branch rules checked for you.</div>
      </div>
    </section>
    <section class="auth-card"><div class="card">
      <div class="tabs"><button class="${reg ? "" : "on"}" data-m="login">Sign in</button><button class="${reg ? "on" : ""}" data-m="register">Create account</button></div>
      <form id="auth-form" novalidate>
        ${reg ? `
        <div class="field"><label>I am a</label><select name="role" id="role"><option value="student">Student</option><option value="recruiter">Recruiter</option></select></div>
        <div class="field"><label>Full name</label><input name="name" required autocomplete="name"></div>` : ""}
        <div class="field"><label>Email</label><input name="email" type="email" required autocomplete="email"></div>
        <div class="field"><label>Password</label><input name="password" type="password" required minlength="6" autocomplete="${reg ? "new-password" : "current-password"}"></div>
        ${reg ? `<div id="role-fields"></div>` : ""}
        <div id="auth-err" class="small" style="color:var(--bad);min-height:1.2em;margin-bottom:.5rem"></div>
        <button class="btn primary" style="width:100%;justify-content:center" type="submit">${reg ? "Create account" : "Sign in"}</button>
      </form>
      ${reg ? "" : `<p class="small muted" style="margin:1rem 0 .25rem">Try a demo account:</p>
      <div class="demo">
        <button class="btn small" data-demo="aarav@campus.edu|student123">Student</button>
        <button class="btn small" data-demo="hr@nimbus.com|recruit123">Recruiter</button>
        <button class="btn small" data-demo="admin@campushire.edu|admin123">Placement admin</button>
      </div>`}
    </div></section>
  </div>`;
  $$(".tabs button").forEach((b) => (b.onclick = () => renderAuth(b.dataset.m)));
  $$("[data-demo]").forEach((b) => (b.onclick = () => {
    const [e, p] = b.dataset.demo.split("|"); const f = $("#auth-form");
    f.email.value = e; f.password.value = p; f.requestSubmit();
  }));
  if (reg) {
    const drawRole = () => {
      $("#role-fields").innerHTML = $("#role").value === "student" ? `
        <div class="form-grid">
          <div class="field"><label>Branch</label><select name="branch">${BRANCHES.map((b) => `<option>${b}</option>`).join("")}</select></div>
          <div class="field"><label>CGPA (0–10)</label><input name="cgpa" type="number" step="0.01" min="0" max="10"></div>
        </div><div class="field"><label>Graduation year</label><input name="grad_year" type="number" min="2000" max="2100" value="${new Date().getFullYear() + 1}"></div>`
        : `<div class="field"><label>Company name</label><input name="company" required></div>`;
    };
    $("#role").onchange = drawRole; drawRole();
  }
  $("#auth-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target, btn = $("button[type=submit]", f), label = btn.textContent;
    const body = Object.fromEntries(new FormData(f)); $("#auth-err").textContent = "";
    btnBusy(btn, true, label);
    try {
      const d = await api(reg ? "/api/register" : "/api/login", { method: "POST", body });
      token = d.token; localStorage.setItem("ch_token", token); await boot();
    } catch (err) { $("#auth-err").textContent = err.message; btnBusy(btn, false, label); }
  };
}

/* ------------------------------------------------------------ shell & router */
const NAV = {
  student: [["dashboard", "Dashboard"], ["jobs", "Jobs"], ["applications", "My applications"], ["profile", "Profile & resume"]],
  recruiter: [["myjobs", "My jobs"], ["post", "Post a job"]],
  admin: [["admin", "Overview"], ["jobs", "All jobs"]],
};
const HOME = { student: "dashboard", recruiter: "myjobs", admin: "admin" };

function renderShell() {
  const u = me.user;
  $("#app").innerHTML = `
  <header class="topbar"><div class="topbar-inner">
    <a class="logo" href="#/${HOME[u.role]}"><i></i>CampusHire</a>
    <nav id="nav">${NAV[u.role].map(([k, l]) => `<a href="#/${k}" data-k="${k}">${l}</a>`).join("")}</nav>
    <div class="userbox"><div class="avatar">${esc(initials(u.name))}</div><div class="small"><b>${esc(u.name)}</b><br><span class="muted" style="text-transform:capitalize">${esc(u.role)}${me.company ? " · " + esc(me.company) : ""}</span></div>
    <button class="btn small" id="logout">Sign out</button></div>
  </div></header><main id="view"></main>`;
  $("#logout").onclick = async () => { try { await api("/api/logout", { method: "POST" }); } catch (_) {} signOutLocal(); };
}

async function render() {
  if (!me) return;
  closeModal();
  const parts = (location.hash.replace(/^#\/?/, "") || HOME[me.user.role]).split("/");
  const [page, arg] = parts;
  $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.k === page || (page === "applicants" && a.dataset.k === "myjobs")));
  const views = {
    student: { dashboard: vDashboard, jobs: vJobs, applications: vApplications, profile: vProfile },
    recruiter: { myjobs: vMyJobs, post: vPostJob, applicants: () => vApplicants(arg), jobs: vJobs },
    admin: { admin: vAdmin, jobs: vJobs, applicants: () => vApplicants(arg) },
  }[me.user.role];
  const fn = views[page] || views[HOME[me.user.role]];
  loading();
  try { await fn(); } catch (e) { setView(`<div class="card empty">${esc(e.message)}</div>`); }
}
window.addEventListener("hashchange", render);

async function boot() {
  if (!token) return renderAuth();
  try { me = await api("/api/me"); } catch (_) { return renderAuth(); }
  renderShell();
  if (!location.hash) location.hash = "#/" + HOME[me.user.role]; else render();
}

/* ------------------------------------------------------------ student: jobs */
function jobCard(j) {
  const m = j.match, student = me.user.role === "student";
  const badge = j.applied ? `<span class="chip brand">Applied</span>`
    : j.expired ? `<span class="chip bad">Deadline passed</span>`
    : student && j.eligible === false ? `<span class="chip bad" title="${esc(j.ineligible_reason)}">Not eligible</span>`
    : student ? `<span class="chip good">Eligible</span>` : "";
  const dl = daysLeft(j.deadline);
  return `<article class="card job" data-id="${j.id}" tabindex="0">
    <div class="body">
      <div class="row between"><h3>${esc(j.title)}</h3>${j.status === "closed" ? `<span class="chip bad">Closed</span>` : ""}</div>
      <div class="meta">${esc(j.company)} · ${esc(j.location || "Location n/a")} · ${esc(j.job_type)} · <b>${money(j.package_lpa)}</b></div>
      <div>${badge} <span class="chip">${dl >= 0 ? (dl === 0 ? "Closes today" : dl + " days left") : "Closed " + fmtDate(j.deadline)}</span>${j.min_cgpa ? `<span class="chip">CGPA ≥ ${j.min_cgpa}</span>` : ""}</div>
      <div style="margin-top:.4rem">${m ? chips(m.matched, "good") + chips(m.related.map((r) => r.skill), "warn") + chips(m.missing.slice(0, 4), "") : chips(j.skills)}</div>
    </div>
    ${m ? `<div style="text-align:center">${ring(m.score)}<div class="small muted" style="margin-top:.2rem">${esc(m.verdict)}</div></div>` : ""}
  </article>`;
}
function bindJobCards(jobs, refresh) {
  $$(".job").forEach((el) => {
    const open = () => showJob(jobs.find((j) => j.id == el.dataset.id), refresh);
    el.onclick = open; el.onkeydown = (e) => { if (e.key === "Enter") open(); };
  });
}
async function vJobs() {
  const student = me.user.role === "student", admin = me.user.role === "admin";
  setView(`<div class="page-head"><div><h1>${student ? "Jobs for you" : "Jobs"}</h1><p class="muted">${student ? "Ranked by how well your resume fits each opening." : "Browse open positions."}</p></div></div>
    <div class="toolbar">
      <input id="q" type="search" placeholder="Search title, company, skill, location…">
      <select id="type"><option value="">All types</option><option>Full-time</option><option>Internship</option><option>Internship + PPO</option></select>
      <select id="sort">${student ? `<option value="match">Best match</option>` : ""}<option value="recent">Newest</option><option value="package">Highest package</option><option value="deadline">Deadline</option></select>
      ${admin ? `<label class="row small" style="margin:0"><input type="checkbox" id="all" style="width:auto"> Include closed</label>` : ""}
    </div><div id="list" class="stack"></div>`);
  let timer;
  const load = async () => {
    const qs = new URLSearchParams({ q: $("#q").value, type: $("#type").value, sort: $("#sort").value });
    if (admin && $("#all")?.checked) qs.set("status", "all");
    const { jobs } = await api("/api/jobs?" + qs);
    $("#list").innerHTML = jobs.length ? jobs.map(jobCard).join("") : `<div class="card empty">No jobs match your filters.</div>`;
    bindJobCards(jobs, load);
  };
  $("#q").oninput = () => { clearTimeout(timer); timer = setTimeout(load, 250); };
  ["type", "sort", "all"].forEach((id) => $("#" + id) && ($("#" + id).onchange = load));
  await load();
}
function meter(label, v) {
  return v == null ? "" : `<div class="meter"><span>${label}</span><div class="bar"><span style="width:${v}%"></span></div><b>${v}%</b></div>`;
}
function showJob(j, refresh) {
  const student = me.user.role === "student", m = j.match;
  const canApply = student && !j.applied && !j.expired && j.status === "open" && j.eligible !== false;
  const o = openModal(`
    <div class="row" style="align-items:flex-start;gap:1rem">
      <div style="flex:1"><h2>${esc(j.title)}</h2><p class="muted">${esc(j.company)} · ${esc(j.location || "Location n/a")} · ${esc(j.job_type)} · <b>${money(j.package_lpa)}</b></p></div>
      ${m ? ring(m.score, 76) : ""}
    </div>
    <div style="margin:.2rem 0 .8rem"><span class="chip">Apply by ${fmtDate(j.deadline)}</span><span class="chip">CGPA ≥ ${j.min_cgpa || 0}</span><span class="chip">${j.branches.length ? esc(j.branches.join(", ")) : "All branches"}</span></div>
    <p style="white-space:pre-wrap">${esc(j.description)}</p>
    <h3>Required skills</h3><div>${chips(j.skills)}</div>
    ${m ? `<hr style="border:0;border-top:1px solid var(--line);margin:1rem 0">
      <div class="row between"><h3 style="margin:0">Your AI match: ${esc(m.verdict)}</h3></div>
      <div style="margin:.5rem 0">${meter("Skills", m.breakdown.skills)}${meter("Resume text fit", m.breakdown.text)}${meter("Academics", m.breakdown.academic)}</div>
      ${m.matched.length ? `<p class="small"><b>You have:</b><br>${chips(m.matched, "good")}</p>` : ""}
      ${m.related.length ? `<p class="small"><b>Related skills (partial credit):</b><br>${m.related.map((r) => `<span class="chip warn">${esc(r.skill)} ← ${esc(r.via.join(", "))}</span>`).join("")}</p>` : ""}
      ${m.missing.length ? `<p class="small"><b>Skill gaps:</b><br>${chips(m.missing, "bad")}</p>` : ""}
      ${m.tips.length ? `<ul class="small muted" style="padding-left:1.1rem;margin:.3rem 0">${m.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}` : ""}
    ${student && j.eligible === false ? `<div class="notice" style="margin:.8rem 0">${esc(j.ineligible_reason)}</div>` : ""}
    <div class="row" style="margin-top:1rem;justify-content:flex-end">
      ${student ? (j.applied ? `<span class="chip brand">You have applied</span>` : `<button class="btn primary" id="apply" ${canApply ? "" : "disabled"}>Apply now</button>`) : ""}
      ${!student && (me.user.role === "admin" || me.user.id === j.recruiter_id) ? `<a class="btn" href="#/applicants/${j.id}">View applicants (${j.applicants ?? 0})</a>` : ""}
    </div>`);
  const btn = $("#apply", o);
  if (btn) btn.onclick = async () => {
    btnBusy(btn, true, "Apply now");
    try { const r = await api(`/api/jobs/${j.id}/apply`, { method: "POST" }); toast(`Applied! Your match score was ${r.match_score}%`); closeModal(); refresh && refresh(); }
    catch (e) { toast(e.message, true); btnBusy(btn, false, "Apply now"); }
  };
}

/* ------------------------------------------------------------ student: dashboard, applications, profile */
async function vDashboard() {
  const [{ jobs }, { applications }] = await Promise.all([api("/api/jobs?sort=match"), api("/api/applications")]);
  const p = me.profile;
  const open = jobs.filter((j) => !j.applied && j.eligible && !j.expired);
  const gaps = {};
  open.slice(0, 5).forEach((j) => j.match.missing.forEach((s) => (gaps[s] = (gaps[s] || 0) + 1)));
  const topGaps = Object.entries(gaps).sort((a, b) => b[1] - a[1]).slice(0, 6).map((e) => e[0]);
  const offers = applications.filter((a) => a.status === "offered").length;
  setView(`
    <div class="page-head"><div><h1>Hi ${esc(me.user.name.split(" ")[0])} 👋</h1><p class="muted">Here is where your placement season stands.</p></div><a class="btn primary" href="#/jobs">Browse all jobs</a></div>
    ${p.completeness < 100 ? `<div class="notice" style="margin-bottom:1rem">Your profile is ${p.completeness}% complete. A full profile and resume give more accurate matches. <a href="#/profile">Finish it</a></div>` : ""}
    <div class="grid cols-4" style="margin-bottom:1rem">
      <div class="card stat"><div class="lbl">Profile strength</div><div class="num">${p.completeness}%</div></div>
      <div class="card stat"><div class="lbl">Applications</div><div class="num">${applications.length}</div></div>
      <div class="card stat"><div class="lbl">In progress</div><div class="num">${applications.filter((a) => ["shortlisted", "interview"].includes(a.status)).length}</div></div>
      <div class="card stat"><div class="lbl">Offers</div><div class="num" style="color:var(--good)">${offers}</div></div>
    </div>
    <div class="grid" style="grid-template-columns:2fr 1fr;gap:1rem" id="dash-grid">
      <section><h2>Top matches you haven't applied to</h2><div class="stack" id="top">${open.slice(0, 4).map(jobCard).join("") || `<div class="card empty">No eligible open jobs right now.</div>`}</div></section>
      <aside class="stack">
        <div class="card"><h2>Skills to build next</h2><p class="small muted">Most-requested gaps across your best-fit jobs.</p>${topGaps.length ? chips(topGaps, "bad") : `<p class="small muted">No gaps - nice work.</p>`}</div>
        <div class="card"><h2>Your skills</h2>${p.skills.length ? chips(p.skills, "brand") : `<p class="small muted">Add skills on your profile.</p>`}</div>
      </aside>
    </div>`);
  if (innerWidth < 860) $("#dash-grid").style.gridTemplateColumns = "1fr";
  bindJobCards(jobs, render);
}
async function vApplications() {
  const { applications } = await api("/api/applications");
  setView(`<div class="page-head"><div><h1>My applications</h1><p class="muted">Track every application through the hiring pipeline.</p></div></div>
  <div class="stack">${applications.length ? applications.map((a) => {
    const idx = FLOW.indexOf(a.status), rej = a.status === "rejected";
    return `<div class="card"><div class="row between"><div><h3 style="margin:0">${esc(a.title)}</h3><span class="muted small">${esc(a.company)} · ${esc(a.location || "")} · ${money(a.package_lpa)} · applied ${fmtDate(a.applied_at)}</span></div>
      <div class="row">${ring(a.match_score, 46)}${pill(a.status)}${a.status === "applied" ? `<button class="btn small danger" data-w="${a.id}">Withdraw</button>` : ""}</div></div>
      <div class="tracker ${rej ? "rejected" : ""}">${FLOW.map((s, i) => `<div class="step ${i <= idx ? "done" : ""} ${i === FLOW.length - 1 ? "final" : ""}">${s}</div>`).join("")}</div>
      ${rej ? `<p class="small" style="color:var(--bad);margin:.5rem 0 0">Not selected for this role. Keep going - your next match is waiting.</p>` : ""}</div>`;
  }).join("") : `<div class="card empty">You haven't applied anywhere yet. <a href="#/jobs">Find a job</a></div>`}</div>`);
  $$("[data-w]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Withdraw this application?")) return;
    try { await api("/api/applications/" + b.dataset.w, { method: "DELETE" }); toast("Application withdrawn"); render(); } catch (e) { toast(e.message, true); }
  }));
}
function analysisHtml(a) {
  const catChips = Object.entries(a.skills_by_category).map(([c, s]) => `<p class="small" style="margin:.2rem 0"><b style="text-transform:capitalize">${esc(c)}:</b> ${chips(s, "brand")}</p>`).join("");
  return `<div class="row" style="gap:1rem;align-items:flex-start">${ring(a.score, 80)}<div style="flex:1"><h3 style="margin:0">Resume score: ${a.score}/100</h3><p class="small muted">${a.word_count} words · ${a.skills.length} skills detected</p></div></div>
    <div style="margin:.8rem 0">${a.checks.map((c) => `<div class="small">${c.passed ? "✅" : "⬜"} ${esc(c.name)} <span class="muted">(${c.points} pts)</span></div>`).join("")}</div>
    ${a.tips.length ? `<h3>How to improve</h3><ul class="small" style="padding-left:1.1rem;margin:.2rem 0">${a.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : `<p class="small" style="color:var(--good)">Looks great - nothing major to fix.</p>`}
    <h3 style="margin-top:.8rem">Detected skills</h3>${catChips || `<p class="small muted">None detected yet.</p>`}`;
}
async function vProfile() {
  const p = me.profile;
  setView(`<div class="page-head"><div><h1>Profile & resume</h1><p class="muted">The matcher reads your resume text and skills. Keep them current.</p></div></div>
  <div class="grid cols-2" style="align-items:start" id="prof-grid">
    <form class="card" id="pform">
      <div class="form-grid">
        <div class="field"><label>Full name</label><input name="name" value="${esc(me.user.name)}" required></div>
        <div class="field"><label>Phone</label><input name="phone" value="${esc(p.phone)}"></div>
        <div class="field"><label>Branch</label><select name="branch">${BRANCHES.map((b) => `<option ${b === p.branch ? "selected" : ""}>${b}</option>`).join("")}</select></div>
        <div class="field"><label>CGPA</label><input name="cgpa" type="number" step="0.01" min="0" max="10" value="${p.cgpa ?? ""}"></div>
        <div class="field"><label>Graduation year</label><input name="grad_year" type="number" min="2000" max="2100" value="${p.grad_year ?? ""}"></div>
      </div>
      <div class="field"><label>Skills (comma separated)</label><input name="skills" id="skills" value="${esc(p.skills.join(", "))}" placeholder="Python, React, SQL…"></div>
      <div class="field"><div class="row between"><label style="margin:0">Resume text</label><label class="btn small" style="margin:0;cursor:pointer">Upload .txt<input type="file" id="file" accept=".txt,.md,text/plain" hidden></label></div>
        <textarea name="resume_text" id="resume" rows="14" placeholder="Paste your resume here (plain text)…">${esc(p.resume_text)}</textarea>
        <p class="small muted" style="margin:.3rem 0 0">Tip: copy the text out of your PDF/Word resume and paste it here.</p></div>
      <div class="row"><button class="btn primary" type="submit">Save profile</button><button class="btn" type="button" id="analyze">Analyze resume</button></div>
    </form>
    <div class="card" id="analysis"><h2>AI resume analysis</h2><p class="muted small">Click <b>Analyze resume</b> to get a score, detected skills and specific improvements.</p></div>
  </div>`);
  if (innerWidth < 860) $("#prof-grid").style.gridTemplateColumns = "1fr";
  $("#file").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    if (f.size > 200000) return toast("File too large (max 200 KB)", true);
    $("#resume").value = await f.text(); toast("Resume loaded - remember to save");
  };
  $("#analyze").onclick = async () => {
    try {
      const a = await api("/api/resume/analyze", { method: "POST", body: { text: $("#resume").value } });
      $("#analysis").innerHTML = `<h2>AI resume analysis</h2>${analysisHtml(a)}
        <button class="btn small" id="addsk" style="margin-top:.8rem">Add detected skills to my profile</button>`;
      $("#addsk").onclick = () => {
        const cur = $("#skills").value.split(",").map((s) => s.trim()).filter(Boolean);
        const have = new Set(cur.map((s) => s.toLowerCase()));
        a.skills.forEach((s) => !have.has(s) && cur.push(s));
        $("#skills").value = cur.join(", "); toast("Skills added - remember to save");
      };
    } catch (e) { toast(e.message, true); }
  };
  $("#pform").onsubmit = async (e) => {
    e.preventDefault();
    const btn = $("button[type=submit]", e.target), body = Object.fromEntries(new FormData(e.target));
    btnBusy(btn, true, "Save profile");
    try { me = await api("/api/profile", { method: "PUT", body }); toast("Profile saved"); renderShell(); $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.k === "profile")); }
    catch (err) { toast(err.message, true); }
    btnBusy(btn, false, "Save profile");
  };
}

/* ------------------------------------------------------------ recruiter */
async function vMyJobs() {
  const { jobs } = await api("/api/my/jobs");
  setView(`<div class="page-head"><div><h1>My jobs</h1><p class="muted">Postings for ${esc(me.company)}.</p></div><a class="btn primary" href="#/post">+ Post a job</a></div>
  <div class="stack">${jobs.length ? jobs.map((j) => `<div class="card">
    <div class="row between"><div><h3 style="margin:0">${esc(j.title)} ${j.status === "closed" ? `<span class="chip bad">Closed</span>` : j.expired ? `<span class="chip warn">Past deadline</span>` : `<span class="chip good">Open</span>`}</h3>
      <span class="muted small">${esc(j.job_type)} · ${money(j.package_lpa)} · deadline ${fmtDate(j.deadline)}</span></div>
      <div class="row"><a class="btn small primary" href="#/applicants/${j.id}">Applicants (${j.applicants})</a>
      <button class="btn small" data-toggle="${j.id}" data-to="${j.status === "open" ? "closed" : "open"}">${j.status === "open" ? "Close" : "Reopen"}</button></div></div>
    <div style="margin-top:.5rem">${chips(j.skills)}</div>
    <div class="small muted" style="margin-top:.3rem">${Object.entries(j.by_status).filter(([, n]) => n).map(([s, n]) => `${n} ${s}`).join(" · ") || "No applicants yet"}</div></div>`).join("")
    : `<div class="card empty">No postings yet. <a href="#/post">Create your first job</a></div>`}</div>`);
  $$("[data-toggle]").forEach((b) => (b.onclick = async () => {
    try { await api(`/api/jobs/${b.dataset.toggle}/status`, { method: "PUT", body: { status: b.dataset.to } }); toast("Updated"); render(); } catch (e) { toast(e.message, true); }
  }));
}
async function vPostJob() {
  const min = new Date(Date.now() + 864e5 * 14).toISOString().slice(0, 10);
  setView(`<div class="page-head"><div><h1>Post a job</h1><p class="muted">Candidates are matched against the skills you list.</p></div></div>
  <form class="card" id="jform">
    <div class="form-grid">
      <div class="field"><label>Job title</label><input name="title" required></div>
      <div class="field"><label>Location</label><input name="location" placeholder="Bengaluru / Remote"></div>
      <div class="field"><label>Type</label><select name="job_type"><option>Full-time</option><option>Internship</option><option>Internship + PPO</option></select></div>
      <div class="field"><label>Package (LPA / stipend)</label><input name="package_lpa" type="number" step="0.1" min="0"></div>
      <div class="field"><label>Minimum CGPA</label><input name="min_cgpa" type="number" step="0.1" min="0" max="10" value="6"></div>
      <div class="field"><label>Application deadline</label><input name="deadline" type="date" required value="${min}"></div>
    </div>
    <div class="field"><label>Eligible branches <span class="muted">(none ticked = all)</span></label><div class="checks">${BRANCHES.map((b) => `<label><input type="checkbox" name="branches" value="${b}">${b}</label>`).join("")}</div></div>
    <div class="field"><label>Description</label><textarea name="description" id="desc" rows="6" required placeholder="What will the candidate do? What tools and technologies do they use?"></textarea></div>
    <div class="field"><div class="row between"><label style="margin:0">Required skills (comma separated)</label><button class="btn small" type="button" id="suggest">✨ Suggest from description</button></div>
      <input name="skills" id="skills" placeholder="python, django, postgresql"><p class="small muted" style="margin:.3rem 0 0">Leave blank to auto-detect from the description.</p></div>
    <button class="btn primary" type="submit">Publish job</button>
  </form>`);
  $("#suggest").onclick = async () => {
    try { const { skills } = await api("/api/skills/extract", { method: "POST", body: { text: $("[name=title]").value + " " + $("#desc").value } });
      if (!skills.length) return toast("No known skills found in the description");
      $("#skills").value = skills.join(", "); toast(`Detected ${skills.length} skills`);
    } catch (e) { toast(e.message, true); }
  };
  $("#jform").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target), body = Object.fromEntries(fd);
    body.branches = fd.getAll("branches");
    const btn = $("button[type=submit]", e.target); btnBusy(btn, true, "Publish job");
    try { await api("/api/jobs", { method: "POST", body }); toast("Job published"); location.hash = "#/myjobs"; }
    catch (err) { toast(err.message, true); btnBusy(btn, false, "Publish job"); }
  };
}
async function vApplicants(id) {
  const { job, applicants } = await api(`/api/jobs/${id}/applicants`);
  setView(`<div class="page-head"><div><a href="#/${me.user.role === "admin" ? "jobs" : "myjobs"}" class="small">← Back</a><h1>${esc(job.title)}</h1><p class="muted">${esc(job.company)} · ${applicants.length} applicant${applicants.length === 1 ? "" : "s"}, ranked by AI match</p></div>
    <div class="row"><label class="small" style="margin:0">Min match <b id="minv">0</b>%</label><input type="range" id="min" min="0" max="100" step="5" value="0" style="width:140px"></div></div>
    <div id="alist" class="stack"></div>`);
  const draw = () => {
    const min = +$("#min").value; $("#minv").textContent = min;
    const list = applicants.filter((a) => a.match.score >= min);
    $("#alist").innerHTML = list.length ? list.map((a, i) => `<div class="card">
      <div class="row" style="align-items:flex-start;gap:1rem">${ring(a.match.score, 64)}
        <div style="flex:1;min-width:200px"><div class="row between"><h3 style="margin:0">#${i + 1} ${esc(a.name)}</h3>${pill(a.status)}</div>
          <p class="small muted" style="margin:.1rem 0 .4rem">${esc(a.branch || "—")} · CGPA ${a.cgpa ?? "—"} · ${esc(a.email)} · <b>${esc(a.match.verdict)}</b></p>
          <div>${chips(a.match.matched, "good")}${chips(a.match.related.map((r) => r.skill), "warn")}${chips(a.match.missing, "bad")}</div></div>
        <div class="stack" style="min-width:150px"><select data-s="${a.id}">${["applied", "shortlisted", "interview", "offered", "rejected"].map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select>
          <button class="btn small" data-r="${a.id}" style="width:100%;justify-content:center">View resume</button></div></div></div>`).join("")
      : `<div class="card empty">No applicants at this match level.</div>`;
    $$("[data-s]").forEach((s) => (s.onchange = async () => {
      try { await api(`/api/applications/${s.dataset.s}/status`, { method: "PUT", body: { status: s.value } }); applicants.find((a) => a.id == s.dataset.s).status = s.value; toast("Status updated → " + s.value); draw(); }
      catch (e) { toast(e.message, true); }
    }));
    $$("[data-r]").forEach((b) => (b.onclick = () => {
      const a = applicants.find((x) => x.id == b.dataset.r);
      openModal(`<h2>${esc(a.name)}</h2><p class="small muted">${esc(a.email)} · ${esc(a.phone || "no phone")} · ${esc(a.branch)} · CGPA ${a.cgpa ?? "—"}</p>
        <div class="meter-block">${meter("Skills", a.match.breakdown.skills)}${meter("Resume text fit", a.match.breakdown.text)}${meter("Academics", a.match.breakdown.academic)}</div>
        <p class="small"><b>Profile skills:</b> ${chips(a.skills, "brand") || "none"}</p><h3>Resume</h3><div class="resume-box">${esc(a.resume_text)}</div>`);
    }));
  };
  $("#min").oninput = draw; draw();
}

/* ------------------------------------------------------------ admin */
async function vAdmin() {
  const s = await api("/api/admin/stats");
  const maxS = Math.max(1, ...Object.values(s.by_status));
  setView(`<div class="page-head"><div><h1>Placement overview</h1><p class="muted">Live numbers for the placement cell.</p></div></div>
  <div class="grid cols-4" style="margin-bottom:1rem">
    <div class="card stat"><div class="lbl">Students</div><div class="num">${s.students}</div></div>
    <div class="card stat"><div class="lbl">Placed</div><div class="num" style="color:var(--good)">${s.placed_students}</div><div class="small muted">${s.placement_rate}% placement rate</div></div>
    <div class="card stat"><div class="lbl">Open jobs</div><div class="num">${s.jobs_open}</div><div class="small muted">${s.recruiters} recruiters · ${s.jobs_closed} closed</div></div>
    <div class="card stat"><div class="lbl">Avg offer</div><div class="num">₹${s.avg_package_lpa}</div><div class="small muted">LPA · avg match ${s.avg_match}%</div></div>
  </div>
  <div class="grid cols-2" style="align-items:start">
    <div class="card"><h2>Applications by stage <span class="muted small">(${s.applications})</span></h2>
      ${Object.entries(s.by_status).map(([k, n]) => `<div class="meter" style="grid-template-columns:90px 1fr 30px"><span style="text-transform:capitalize">${k}</span><div class="bar ${k === "offered" ? "good" : ""}"><span style="width:${(n / maxS) * 100}%"></span></div><b>${n}</b></div>`).join("")}</div>
    <div class="card"><h2>By branch</h2><div class="table-wrap"><table><thead><tr><th>Branch</th><th>Students</th><th>Placed</th><th>Rate</th></tr></thead><tbody>
      ${s.branches.map((b) => `<tr><td><b>${esc(b.branch)}</b></td><td>${b.students}</td><td>${b.placed}</td><td>${b.students ? Math.round((100 * b.placed) / b.students) : 0}%</td></tr>`).join("")}</tbody></table></div></div>
  </div>
  <div class="card" style="margin-top:1rem"><h2>Recruiters</h2><div class="table-wrap"><table><thead><tr><th>Company</th><th>Jobs</th><th>Applications</th><th>Offers</th></tr></thead><tbody>
    ${s.companies.map((c) => `<tr><td><b>${esc(c.company)}</b></td><td>${c.jobs}</td><td>${c.applications}</td><td>${c.offers}</td></tr>`).join("")}</tbody></table></div></div>`);
}

boot();
