import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student','recruiter','admin')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS students (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    branch TEXT DEFAULT '',
    cgpa REAL,
    grad_year INTEGER,
    phone TEXT DEFAULT '',
    skills TEXT NOT NULL DEFAULT '[]',
    resume_text TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS companies (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    description TEXT NOT NULL,
    skills TEXT NOT NULL DEFAULT '[]',
    min_cgpa REAL NOT NULL DEFAULT 0,
    branches TEXT NOT NULL DEFAULT '[]',
    package_lpa REAL NOT NULL DEFAULT 0,
    location TEXT DEFAULT '',
    job_type TEXT NOT NULL DEFAULT 'Full-time',
    deadline TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'applied',
    match_score INTEGER NOT NULL DEFAULT 0,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (job_id, student_id)
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_apps_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_apps_student ON applications(student_id);
"""


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path):
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
