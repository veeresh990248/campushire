#!/usr/bin/env python3
"""CampusHire - placement portal with an AI resume matcher.

Zero-dependency server: Python standard library + SQLite. Run:  python server.py
"""
import argparse
import json
import mimetypes
import os
import re
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import auth
import db as dbm
import matcher
import seed as seedmod

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
STATUSES = ("applied", "shortlisted", "interview", "offered", "rejected")
JOB_TYPES = ("Full-time", "Internship", "Internship + PPO")
MAX_BODY = 1_000_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


ROUTES = []


def route(method, pattern, roles=None):
    """roles: None = public, 'any' = any signed-in user, or a tuple of allowed roles."""
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), roles, fn))
        return fn
    return deco


class Ctx:
    def __init__(self, db, user, body, query):
        self.db, self.user, self.body, self.query = db, user, body, query


# ---------------------------------------------------------------- helpers
def need(body, key, label=None, maxlen=200):
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ApiError(400, f"{label or key} is required")
    v = v.strip()
    if len(v) > maxlen:
        raise ApiError(400, f"{label or key} is too long")
    return v


def parse_float(v, label, lo, hi, required=False):
    if v in (None, ""):
        if required:
            raise ApiError(400, f"{label} is required")
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ApiError(400, f"{label} must be a number")
    if not lo <= f <= hi:
        raise ApiError(400, f"{label} must be between {lo} and {hi}")
    return f


def skill_list(v):
    if isinstance(v, str):
        v = v.split(",")
    if not isinstance(v, list):
        raise ApiError(400, "skills must be a list")
    out = []
    for s in v:
        s = matcher.normalize_skill(s)
        if s and len(s) <= 40 and s not in out:
            out.append(s)
    return out[:50]


def user_public(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]}


def student_row(db, uid):
    r = db.execute("SELECT * FROM students WHERE user_id=?", (uid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["skills"] = json.loads(d["skills"] or "[]")
    return d


def completeness(p):
    checks = [bool(p["branch"]), p["cgpa"] is not None, bool(p["grad_year"]), bool(p["phone"]),
              len(p["skills"]) >= 3, len(p["resume_text"]) >= 100]
    return int(round(100 * sum(checks) / len(checks)))


def job_dict(row):
    d = dict(row)
    d["skills"] = json.loads(d["skills"] or "[]")
    d["branches"] = json.loads(d["branches"] or "[]")
    d["expired"] = d["deadline"] < date.today().isoformat()
    return d


def eligibility(student, job):
    if student["cgpa"] is None or not student["branch"]:
        return False, "Complete your profile (branch and CGPA) to check eligibility"
    if student["cgpa"] < job["min_cgpa"]:
        return False, f"Minimum CGPA is {job['min_cgpa']:g}"
    if job["branches"] and student["branch"].upper() not in [b.upper() for b in job["branches"]]:
        return False, "Open to " + ", ".join(job["branches"]) + " only"
    return True, ""


def job_idf(db):
    rows = db.execute("SELECT title, description, skills FROM jobs").fetchall()
    return matcher.build_idf([f"{r['title']} {r['description']} {r['skills']}" for r in rows])


def match_for(student, job, idf):
    return matcher.score_match(student["resume_text"], student["skills"], job, idf, student["cgpa"])


def get_job(db, job_id):
    r = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not r:
        raise ApiError(404, "Job not found")
    return job_dict(r)


def own_job(ctx, job_id):
    job = get_job(ctx.db, job_id)
    if ctx.user["role"] != "admin" and job["recruiter_id"] != ctx.user["id"]:
        raise ApiError(403, "You can only manage your own jobs")
    return job


# ---------------------------------------------------------------- auth
@route("POST", "/api/register")
def register(ctx):
    b = ctx.body
    name = need(b, "name", "Name", 80)
    email = need(b, "email", "Email", 120).lower()
    password = b.get("password") or ""
    role = b.get("role")
    if not EMAIL_RE.match(email):
        raise ApiError(400, "Enter a valid email address")
    if len(password) < 6:
        raise ApiError(400, "Password must be at least 6 characters")
    if role not in ("student", "recruiter"):
        raise ApiError(400, "Role must be student or recruiter")
    if ctx.db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        raise ApiError(409, "An account with this email already exists")
    extra = {}
    if role == "student":
        extra["branch"] = (b.get("branch") or "").strip().upper()[:40]
        extra["cgpa"] = parse_float(b.get("cgpa"), "CGPA", 0, 10)
        gy = b.get("grad_year")
        extra["grad_year"] = int(gy) if str(gy or "").isdigit() and 2000 <= int(gy) <= 2100 else None
    else:
        extra["company"] = need(b, "company", "Company name", 100)
    h, s = auth.hash_password(password)
    uid = ctx.db.execute("INSERT INTO users (name,email,pw_hash,salt,role) VALUES (?,?,?,?,?)",
                         (name, email, h, s, role)).lastrowid
    if role == "student":
        ctx.db.execute("INSERT INTO students (user_id,branch,cgpa,grad_year) VALUES (?,?,?,?)",
                       (uid, extra["branch"], extra["cgpa"], extra["grad_year"]))
    else:
        ctx.db.execute("INSERT INTO companies (user_id,company_name) VALUES (?,?)", (uid, extra["company"]))
    token = auth.new_token()
    ctx.db.execute("INSERT INTO sessions (token,user_id) VALUES (?,?)", (token, uid))
    ctx.db.commit()
    return 201, {"token": token, "user": {"id": uid, "name": name, "email": email, "role": role}}


@route("POST", "/api/login")
def login(ctx):
    email = (ctx.body.get("email") or "").strip().lower()
    row = ctx.db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not auth.verify_password(ctx.body.get("password") or "", row["pw_hash"], row["salt"]):
        raise ApiError(401, "Invalid email or password")
    token = auth.new_token()
    ctx.db.execute("INSERT INTO sessions (token,user_id) VALUES (?,?)", (token, row["id"]))
    ctx.db.commit()
    return {"token": token, "user": user_public(row)}


@route("POST", "/api/logout", "any")
def logout(ctx):
    ctx.db.execute("DELETE FROM sessions WHERE token=?", (ctx.user["token"],))
    ctx.db.commit()
    return {"ok": True}


@route("GET", "/api/me", "any")
def me(ctx):
    out = {"user": user_public(ctx.user)}
    if ctx.user["role"] == "student":
        p = student_row(ctx.db, ctx.user["id"])
        p["completeness"] = completeness(p)
        out["profile"] = p
    elif ctx.user["role"] == "recruiter":
        c = ctx.db.execute("SELECT company_name FROM companies WHERE user_id=?", (ctx.user["id"],)).fetchone()
        out["company"] = c["company_name"] if c else ""
    return out


# ---------------------------------------------------------------- student profile & AI tools
@route("PUT", "/api/profile", ("student",))
def update_profile(ctx):
    b = ctx.body
    cur = student_row(ctx.db, ctx.user["id"])
    name = need(b, "name", "Name", 80) if "name" in b else ctx.user["name"]
    branch = (b.get("branch", cur["branch"]) or "").strip().upper()[:40]
    cgpa = parse_float(b["cgpa"], "CGPA", 0, 10) if "cgpa" in b else cur["cgpa"]
    gy = cur["grad_year"]
    if "grad_year" in b:
        g = str(b["grad_year"] or "")
        if g and not (g.isdigit() and 2000 <= int(g) <= 2100):
            raise ApiError(400, "Graduation year must be between 2000 and 2100")
        gy = int(g) if g else None
    phone = (b.get("phone", cur["phone"]) or "").strip()[:20]
    skills = skill_list(b["skills"]) if "skills" in b else cur["skills"]
    resume = b.get("resume_text", cur["resume_text"]) or ""
    if not isinstance(resume, str) or len(resume) > 20000:
        raise ApiError(400, "Resume text must be under 20,000 characters")
    ctx.db.execute("UPDATE users SET name=? WHERE id=?", (name, ctx.user["id"]))
    ctx.db.execute("UPDATE students SET branch=?, cgpa=?, grad_year=?, phone=?, skills=?, resume_text=? "
                   "WHERE user_id=?", (branch, cgpa, gy, phone, json.dumps(skills), resume, ctx.user["id"]))
    ctx.db.commit()
    ctx.user["name"] = name
    return me(ctx)


@route("POST", "/api/resume/analyze", "any")
def analyze(ctx):
    text = ctx.body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ApiError(400, "Paste your resume text to analyze")
    if len(text) > 20000:
        raise ApiError(400, "Resume text must be under 20,000 characters")
    return matcher.analyze_resume(text)


@route("POST", "/api/skills/extract", "any")
def extract(ctx):
    text = ctx.body.get("text")
    if not isinstance(text, str):
        raise ApiError(400, "text is required")
    return {"skills": matcher.extract_skills(text[:20000])}


# ---------------------------------------------------------------- jobs
@route("GET", "/api/jobs", "any")
def list_jobs(ctx):
    q = (ctx.query.get("q") or "").strip().lower()
    sort = ctx.query.get("sort") or ("match" if ctx.user["role"] == "student" else "recent")
    jtype = ctx.query.get("type") or ""
    show_all = ctx.user["role"] == "admin" and ctx.query.get("status") == "all"
    rows = ctx.db.execute("SELECT * FROM jobs" + ("" if show_all else " WHERE status='open'") +
                          " ORDER BY id DESC").fetchall()
    counts = {r["job_id"]: r["n"] for r in ctx.db.execute(
        "SELECT job_id, COUNT(*) n FROM applications GROUP BY job_id")}
    student = student_row(ctx.db, ctx.user["id"]) if ctx.user["role"] == "student" else None
    applied = set()
    if student:
        applied = {r["job_id"] for r in ctx.db.execute(
            "SELECT job_id FROM applications WHERE student_id=?", (ctx.user["id"],))}
    idf = job_idf(ctx.db) if student else None
    out = []
    for r in rows:
        j = job_dict(r)
        hay = f"{j['title']} {j['company']} {j['location']} {' '.join(j['skills'])}".lower()
        if q and q not in hay:
            continue
        if jtype and j["job_type"] != jtype:
            continue
        j["applicants"] = counts.get(j["id"], 0)
        if student:
            ok, why = eligibility(student, j)
            j["eligible"], j["ineligible_reason"] = ok, why
            j["applied"] = j["id"] in applied
            j["match"] = match_for(student, j, idf)
        out.append(j)
    keys = {
        "match": lambda j: -(j.get("match") or {}).get("score", 0),
        "package": lambda j: -j["package_lpa"],
        "deadline": lambda j: j["deadline"],
        "recent": lambda j: -j["id"],
    }
    out.sort(key=keys.get(sort, keys["recent"]))
    return {"jobs": out}


@route("GET", r"/api/jobs/(?P<job_id>\d+)", "any")
def job_detail(ctx, job_id):
    j = get_job(ctx.db, int(job_id))
    j["applicants"] = ctx.db.execute("SELECT COUNT(*) FROM applications WHERE job_id=?", (j["id"],)).fetchone()[0]
    if ctx.user["role"] == "student":
        s = student_row(ctx.db, ctx.user["id"])
        j["eligible"], j["ineligible_reason"] = eligibility(s, j)
        j["applied"] = bool(ctx.db.execute("SELECT 1 FROM applications WHERE job_id=? AND student_id=?",
                                           (j["id"], ctx.user["id"])).fetchone())
        j["match"] = match_for(s, j, job_idf(ctx.db))
    return j


@route("POST", "/api/jobs", ("recruiter",))
def create_job(ctx):
    b = ctx.body
    title = need(b, "title", "Job title", 120)
    desc = need(b, "description", "Description", 8000)
    if len(desc) < 20:
        raise ApiError(400, "Description should be at least 20 characters")
    deadline = need(b, "deadline", "Deadline", 10)
    if not DATE_RE.match(deadline):
        raise ApiError(400, "Deadline must be YYYY-MM-DD")
    if deadline < date.today().isoformat():
        raise ApiError(400, "Deadline cannot be in the past")
    jtype = b.get("job_type") or "Full-time"
    if jtype not in JOB_TYPES:
        raise ApiError(400, "Invalid job type")
    branches = b.get("branches") or []
    if not isinstance(branches, list):
        raise ApiError(400, "branches must be a list")
    branches = [str(x).strip().upper()[:40] for x in branches if str(x).strip()]
    skills = skill_list(b.get("skills") or [])
    if not skills:
        skills = matcher.extract_skills(f"{title} {desc}")
    min_cgpa = parse_float(b.get("min_cgpa"), "Minimum CGPA", 0, 10) or 0
    lpa = parse_float(b.get("package_lpa"), "Package", 0, 1000) or 0
    company = ctx.db.execute("SELECT company_name FROM companies WHERE user_id=?", (ctx.user["id"],)).fetchone()
    jid = ctx.db.execute(
        "INSERT INTO jobs (recruiter_id,title,company,description,skills,min_cgpa,branches,package_lpa,location,"
        "job_type,deadline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ctx.user["id"], title, company["company_name"] if company else ctx.user["name"], desc,
         json.dumps(skills), min_cgpa, json.dumps(branches), lpa, (b.get("location") or "").strip()[:80],
         jtype, deadline)).lastrowid
    ctx.db.commit()
    return 201, get_job(ctx.db, jid)


@route("PUT", r"/api/jobs/(?P<job_id>\d+)/status", ("recruiter", "admin"))
def set_job_status(ctx, job_id):
    job = own_job(ctx, int(job_id))
    status = ctx.body.get("status")
    if status not in ("open", "closed"):
        raise ApiError(400, "Status must be open or closed")
    ctx.db.execute("UPDATE jobs SET status=? WHERE id=?", (status, job["id"]))
    ctx.db.commit()
    return get_job(ctx.db, job["id"])


@route("GET", "/api/my/jobs", ("recruiter",))
def my_jobs(ctx):
    rows = ctx.db.execute("SELECT * FROM jobs WHERE recruiter_id=? ORDER BY id DESC", (ctx.user["id"],)).fetchall()
    out = []
    for r in rows:
        j = job_dict(r)
        by = {s: 0 for s in STATUSES}
        for a in ctx.db.execute("SELECT status, COUNT(*) n FROM applications WHERE job_id=? GROUP BY status",
                                (j["id"],)):
            by[a["status"]] = a["n"]
        j["by_status"], j["applicants"] = by, sum(by.values())
        out.append(j)
    return {"jobs": out}


# ---------------------------------------------------------------- applications
@route("POST", r"/api/jobs/(?P<job_id>\d+)/apply", ("student",))
def apply(ctx, job_id):
    job = get_job(ctx.db, int(job_id))
    s = student_row(ctx.db, ctx.user["id"])
    if job["status"] != "open" or job["expired"]:
        raise ApiError(400, "Applications for this job are closed")
    ok, why = eligibility(s, job)
    if not ok:
        raise ApiError(403, why)
    if len(s["resume_text"].strip()) < 50:
        raise ApiError(400, "Add your resume text on the Profile page before applying")
    if ctx.db.execute("SELECT 1 FROM applications WHERE job_id=? AND student_id=?",
                      (job["id"], ctx.user["id"])).fetchone():
        raise ApiError(409, "You have already applied to this job")
    score = match_for(s, job, job_idf(ctx.db))["score"]
    aid = ctx.db.execute("INSERT INTO applications (job_id,student_id,match_score) VALUES (?,?,?)",
                         (job["id"], ctx.user["id"], score)).lastrowid
    ctx.db.commit()
    return 201, {"id": aid, "status": "applied", "match_score": score}


@route("GET", "/api/applications", ("student",))
def my_applications(ctx):
    rows = ctx.db.execute(
        "SELECT a.id, a.status, a.match_score, a.applied_at, j.id job_id, j.title, j.company, j.package_lpa, "
        "j.location, j.deadline FROM applications a JOIN jobs j ON j.id=a.job_id "
        "WHERE a.student_id=? ORDER BY a.id DESC", (ctx.user["id"],)).fetchall()
    return {"applications": [dict(r) for r in rows]}


@route("DELETE", r"/api/applications/(?P<app_id>\d+)", ("student",))
def withdraw(ctx, app_id):
    a = ctx.db.execute("SELECT * FROM applications WHERE id=? AND student_id=?",
                       (int(app_id), ctx.user["id"])).fetchone()
    if not a:
        raise ApiError(404, "Application not found")
    if a["status"] != "applied":
        raise ApiError(400, "You can only withdraw applications that have not been reviewed yet")
    ctx.db.execute("DELETE FROM applications WHERE id=?", (a["id"],))
    ctx.db.commit()
    return {"ok": True}


@route("GET", r"/api/jobs/(?P<job_id>\d+)/applicants", ("recruiter", "admin"))
def applicants(ctx, job_id):
    job = own_job(ctx, int(job_id))
    idf = job_idf(ctx.db)
    out = []
    for a in ctx.db.execute(
            "SELECT a.id, a.status, a.applied_at, u.id uid, u.name, u.email FROM applications a "
            "JOIN users u ON u.id=a.student_id WHERE a.job_id=?", (job["id"],)):
        s = student_row(ctx.db, a["uid"])
        out.append({"id": a["id"], "status": a["status"], "applied_at": a["applied_at"], "name": a["name"],
                    "email": a["email"], "branch": s["branch"], "cgpa": s["cgpa"], "phone": s["phone"],
                    "grad_year": s["grad_year"], "skills": s["skills"], "resume_text": s["resume_text"],
                    "match": match_for(s, job, idf)})
    out.sort(key=lambda x: -x["match"]["score"])
    return {"job": job, "applicants": out}


@route("PUT", r"/api/applications/(?P<app_id>\d+)/status", ("recruiter", "admin"))
def set_app_status(ctx, app_id):
    a = ctx.db.execute("SELECT * FROM applications WHERE id=?", (int(app_id),)).fetchone()
    if not a:
        raise ApiError(404, "Application not found")
    own_job(ctx, a["job_id"])
    status = ctx.body.get("status")
    if status not in STATUSES:
        raise ApiError(400, "Invalid status")
    ctx.db.execute("UPDATE applications SET status=? WHERE id=?", (status, a["id"]))
    ctx.db.commit()
    return {"id": a["id"], "status": status}


# ---------------------------------------------------------------- admin
@route("GET", "/api/admin/stats", ("admin",))
def stats(ctx):
    q = lambda sql, *a: ctx.db.execute(sql, a).fetchall()
    one = lambda sql, *a: ctx.db.execute(sql, a).fetchone()[0]
    students = one("SELECT COUNT(*) FROM users WHERE role='student'")
    placed = one("SELECT COUNT(DISTINCT student_id) FROM applications WHERE status='offered'")
    by_status = {s: 0 for s in STATUSES}
    for r in q("SELECT status, COUNT(*) n FROM applications GROUP BY status"):
        by_status[r["status"]] = r["n"]
    branches = []
    for r in q("SELECT UPPER(COALESCE(NULLIF(s.branch,''),'N/A')) b, COUNT(*) n, "
               "COUNT(DISTINCT CASE WHEN a.status='offered' THEN s.user_id END) placed "
               "FROM students s LEFT JOIN applications a ON a.student_id=s.user_id GROUP BY b ORDER BY n DESC"):
        branches.append({"branch": r["b"], "students": r["n"], "placed": r["placed"]})
    # the LEFT JOIN duplicates student rows per application, so recount students per branch exactly
    for b in branches:
        b["students"] = one("SELECT COUNT(*) FROM students WHERE UPPER(COALESCE(NULLIF(branch,''),'N/A'))=?",
                            b["branch"])
    companies = [dict(r) for r in q(
        "SELECT j.company, COUNT(DISTINCT j.id) jobs, COUNT(a.id) applications, "
        "SUM(CASE WHEN a.status='offered' THEN 1 ELSE 0 END) offers FROM jobs j "
        "LEFT JOIN applications a ON a.job_id=j.id GROUP BY j.company ORDER BY offers DESC, applications DESC")]
    for c in companies:
        c["offers"] = c["offers"] or 0
    avg_pkg = one("SELECT AVG(j.package_lpa) FROM applications a JOIN jobs j ON j.id=a.job_id "
                  "WHERE a.status='offered'")
    return {
        "students": students, "recruiters": one("SELECT COUNT(*) FROM users WHERE role='recruiter'"),
        "jobs_open": one("SELECT COUNT(*) FROM jobs WHERE status='open'"),
        "jobs_closed": one("SELECT COUNT(*) FROM jobs WHERE status='closed'"),
        "applications": sum(by_status.values()), "by_status": by_status,
        "placed_students": placed, "placement_rate": round(100 * placed / students, 1) if students else 0,
        "avg_package_lpa": round(avg_pkg, 2) if avg_pkg else 0,
        "avg_match": round(one("SELECT COALESCE(AVG(match_score),0) FROM applications"), 1),
        "branches": branches, "companies": companies,
    }


# ---------------------------------------------------------------- HTTP plumbing
def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CampusHire/1.0"

        def log_message(self, fmt, *args):
            if os.environ.get("CAMPUSHIRE_QUIET") != "1":
                sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def send_json(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def handle_api(self, method, parsed):
            path = parsed.path.rstrip("/") or "/"
            matched_path = False
            for m, pat, roles, fn in ROUTES:
                mo = pat.match(path)
                if not mo:
                    continue
                matched_path = True
                if m != method:
                    continue
                db = dbm.connect(db_path)
                try:
                    user = None
                    if roles is not None:
                        h = self.headers.get("Authorization", "")
                        token = h[7:] if h.startswith("Bearer ") else ""
                        row = db.execute("SELECT u.*, s.token FROM sessions s JOIN users u ON u.id=s.user_id "
                                         "WHERE s.token=?", (token,)).fetchone() if token else None
                        if not row:
                            raise ApiError(401, "Please sign in")
                        user = dict(row)
                        if roles != "any" and user["role"] not in roles:
                            raise ApiError(403, "You don't have access to this")
                    body = {}
                    if method in ("POST", "PUT"):
                        n = int(self.headers.get("Content-Length") or 0)
                        if n > MAX_BODY:
                            raise ApiError(413, "Request too large")
                        if n:
                            try:
                                body = json.loads(self.rfile.read(n) or b"{}")
                            except ValueError:
                                raise ApiError(400, "Invalid JSON")
                            if not isinstance(body, dict):
                                raise ApiError(400, "JSON object expected")
                    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                    result = fn(Ctx(db, user, body, query), **mo.groupdict())
                    status, data = result if isinstance(result, tuple) else (200, result)
                    return self.send_json(status, data)
                except ApiError as e:
                    return self.send_json(e.status, {"error": e.message})
                except Exception as e:  # pragma: no cover - last-resort guard
                    sys.stderr.write(f"Unhandled error: {e!r}\n")
                    return self.send_json(500, {"error": "Something went wrong on our side"})
                finally:
                    db.close()
            self.send_json(405 if matched_path else 404,
                           {"error": "Method not allowed" if matched_path else "Not found"})

        def serve_static(self, path):
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            full = os.path.realpath(os.path.join(STATIC, rel))
            if not full.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(full):
                full = os.path.join(STATIC, "index.html")  # SPA fallback
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", (mimetypes.guess_type(full)[0] or "application/octet-stream")
                             + ("; charset=utf-8" if full.endswith((".html", ".js", ".css")) else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def dispatch(self, method):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                return self.handle_api(method, parsed)
            if method == "GET":
                return self.serve_static(parsed.path)
            self.send_json(405, {"error": "Method not allowed"})

        def do_GET(self): self.dispatch("GET")
        def do_POST(self): self.dispatch("POST")
        def do_PUT(self): self.dispatch("PUT")
        def do_DELETE(self): self.dispatch("DELETE")

    return Handler


def create_server(db_path, host="127.0.0.1", port=8000, seed_demo=True):
    dbm.init_db(db_path)
    if seed_demo:
        conn = dbm.connect(db_path)
        seedmod.seed(conn)
        conn.close()
    return ThreadingHTTPServer((host, port), make_handler(db_path))


def main():
    ap = argparse.ArgumentParser(description="CampusHire placement portal")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--db", default=os.environ.get("CAMPUSHIRE_DB", os.path.join(BASE, "campushire.db")))
    ap.add_argument("--no-seed", action="store_true", help="don't load demo data into an empty database")
    args = ap.parse_args()
    srv = create_server(args.db, args.host, args.port, not args.no_seed)
    print(f"CampusHire running at http://{args.host}:{args.port}  (db: {args.db})  Ctrl+C to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
