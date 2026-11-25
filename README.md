# CampusHire – Placement Portal with AI Resume Matcher

A full-stack campus placement portal. Students see how well their resume fits every job *before* applying, recruiters get applicants ranked by fit, and the placement cell gets live statistics.

**Zero dependencies** – Python 3.9+ standard library, SQLite and vanilla JavaScript. No `pip install`, no build step.

## Run it

```bash
cd campushire
python3 server.py            # http://127.0.0.1:8000
```

Demo data is loaded automatically on first run. Options: `--port 9000`, `--db path/to/file.db`, `--no-seed`.
To reset, delete `campushire.db`.

### Demo accounts

| Role | Email | Password |
|---|---|---|
| Student (CSE, backend skills) | `aarav@campus.edu` | `student123` |
| Student (ML) | `ananya@campus.edu` | `student123` |
| Student (ECE / embedded) | `sneha@campus.edu` | `student123` |
| Recruiter (Nimbus Cloud) | `hr@nimbus.com` | `recruit123` |
| Placement admin (TPO) | `admin@campushire.edu` | `admin123` |

Other seeded students: priya, rohan, karan (`@campus.edu`). Other recruiters: `talent@pixelco.com`, `campus@finedge.com`, `jobs@cortex.ai`, `hiring@voltix.com`, `careers@torque.com`.

## Features

**Students**
- Profile (branch, CGPA, graduation year, skills) and resume text (paste or upload `.txt`)
- **AI job matching** – every job shows a 0–100 match with matched skills, related skills, skill gaps and tips
- **Resume analyzer** – score out of 100, detected skills by category, specific fixes, one-click "add detected skills"
- Automatic eligibility check (minimum CGPA, allowed branches, deadline)
- Apply / withdraw, and an application pipeline tracker (applied → shortlisted → interview → offered)
- Dashboard with "skills to build next", derived from gaps across your best-fit jobs

**Recruiters**
- Post jobs with CGPA cut-off, branches, package and deadline; "✨ Suggest skills from description"
- Applicants **ranked by AI match**, with a minimum-match slider, resume viewer and status updates
- Close / reopen postings

**Placement admin**
- Placement rate, average offer, applications by stage, per-branch and per-recruiter tables
- Browse all jobs including closed ones

## How the matcher works (`matcher.py`)

`score = 0.65 × skill coverage + 0.25 × text similarity + 0.10 × academic fit`

1. **Skill coverage** – a taxonomy of ~100 skills with aliases (`postgres` → `postgresql`, `k8s` → `kubernetes`) is used to extract skills from the resume text; they are merged with the skills on the profile. Each required skill counts 1.0 if present, **0.3 if you have a related skill in the same category** (e.g. job wants MySQL, you know PostgreSQL), else 0.
2. **Text similarity** – TF-IDF cosine similarity between resume and job text (IDF computed over all postings), scaled so a realistic ceiling maps to 100%.
3. **Academic fit** – CGPA relative to the job's cut-off.

If a job lists no skills they are auto-extracted from its description. Every result is explainable: matched / related / missing skills, a per-signal breakdown and a verdict (Strong ≥ 75, Good ≥ 55, Partial ≥ 35, Low).

To add skills, edit `SKILL_TAXONOMY` at the top of `matcher.py`.

> It is a transparent, deterministic scorer rather than an LLM. That keeps it fast, free, offline and auditable – important when it influences hiring decisions. The `score_match` function is the single seam if you later want to blend in an embedding model or LLM.

## Project layout

```
server.py     HTTP server, REST API, auth, static files
matcher.py    skill extraction, TF-IDF, scoring, resume analysis
db.py         SQLite schema        auth.py   PBKDF2 hashing, session tokens
seed.py       demo data
static/       index.html, style.css, app.js  (single-page app)
tests/        24 tests (matcher unit tests + end-to-end API tests)
```

## API (JSON, `Authorization: Bearer <token>`)

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/register`, `/api/login`, `/api/logout` | public / any | accounts |
| `GET /api/me`, `PUT /api/profile` | any / student | profile |
| `POST /api/resume/analyze`, `/api/skills/extract` | any | AI helpers |
| `GET /api/jobs?q=&type=&sort=match\|recent\|package\|deadline` | any | list (students get match + eligibility) |
| `GET /api/jobs/:id` | any | detail |
| `POST /api/jobs`, `PUT /api/jobs/:id/status`, `GET /api/my/jobs` | recruiter | manage postings |
| `POST /api/jobs/:id/apply`, `GET /api/applications`, `DELETE /api/applications/:id` | student | applying |
| `GET /api/jobs/:id/applicants`, `PUT /api/applications/:id/status` | recruiter (owner) / admin | review |
| `GET /api/admin/stats` | admin | analytics |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Security notes

Passwords are PBKDF2-SHA256 hashed with per-user salts; all SQL is parameterised; all rendered text is HTML-escaped; recruiters can only touch their own jobs; static serving blocks path traversal. For a real deployment, put it behind HTTPS (a reverse proxy), add session expiry and rate limiting on login, and consider PostgreSQL instead of SQLite.

## Ideas for next steps

PDF resume parsing (e.g. `pypdf`), email notifications, interview scheduling, company-wise eligibility drives, embedding-based semantic matching.
