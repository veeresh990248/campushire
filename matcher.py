"""CampusHire AI matching engine.

Pure-Python (no third-party packages). Combines three signals:

  1. Skill coverage   - how many of the job's required skills the candidate has,
                        with partial credit for related skills in the same category
  2. Text similarity  - TF-IDF cosine similarity between resume and job description
  3. Academic fit     - CGPA relative to the job's minimum cutoff

and returns an explainable result (matched / related / missing skills, a
per-signal breakdown and a verdict) instead of a bare number.
"""
import math
import re
from collections import Counter

# canonical skill -> (category, [aliases])
SKILL_TAXONOMY = {
    # languages
    "python": ("language", ["python3"]),
    "java": ("language", []),
    "javascript": ("language", ["js", "es6", "ecmascript"]),
    "typescript": ("language", ["ts"]),
    "c": ("language", ["c programming", "c language"]),
    "c++": ("language", ["cpp"]),
    "c#": ("language", ["csharp"]),
    "go": ("language", ["golang", "go language"]),
    "rust": ("language", []),
    "kotlin": ("language", []),
    "swift": ("language", []),
    "php": ("language", []),
    "ruby": ("language", []),
    "r": ("language", ["r programming", "r language"]),
    "scala": ("language", []),
    "matlab": ("language", []),
    "bash": ("language", ["shell scripting"]),
    # frontend
    "html": ("frontend", ["html5"]),
    "css": ("frontend", ["css3"]),
    "react": ("frontend", ["reactjs", "react.js"]),
    "angular": ("frontend", ["angularjs"]),
    "vue": ("frontend", ["vuejs", "vue.js"]),
    "next.js": ("frontend", ["nextjs"]),
    "tailwind": ("frontend", ["tailwindcss"]),
    "bootstrap": ("frontend", []),
    "redux": ("frontend", []),
    # backend
    "node.js": ("backend", ["nodejs", "node js", "node"]),
    "express": ("backend", ["express.js", "expressjs"]),
    "django": ("backend", []),
    "flask": ("backend", []),
    "fastapi": ("backend", []),
    "spring boot": ("backend", ["springboot", "spring framework"]),
    "rest api": ("backend", ["rest apis", "restful", "restful apis", "restful api"]),
    "graphql": ("backend", []),
    "microservices": ("backend", ["microservice"]),
    "asp.net": ("backend", [".net", "dotnet"]),
    "laravel": ("backend", []),
    # databases
    "sql": ("database", []),
    "mysql": ("database", []),
    "postgresql": ("database", ["postgres"]),
    "mongodb": ("database", ["mongo"]),
    "redis": ("database", []),
    "sqlite": ("database", []),
    "oracle": ("database", []),
    "firebase": ("database", []),
    "dbms": ("database", ["database management"]),
    # cloud / devops
    "aws": ("cloud", ["amazon web services"]),
    "azure": ("cloud", ["microsoft azure"]),
    "gcp": ("cloud", ["google cloud"]),
    "docker": ("devops", []),
    "kubernetes": ("devops", ["k8s"]),
    "jenkins": ("devops", []),
    "ci/cd": ("devops", ["cicd", "ci cd"]),
    "terraform": ("devops", []),
    "linux": ("devops", ["unix"]),
    "git": ("tools", ["github", "gitlab"]),
    # ML / data
    "machine learning": ("ml", ["ml"]),
    "deep learning": ("ml", []),
    "nlp": ("ml", ["natural language processing"]),
    "computer vision": ("ml", ["opencv"]),
    "tensorflow": ("ml", ["keras"]),
    "pytorch": ("ml", []),
    "scikit-learn": ("ml", ["sklearn"]),
    "llm": ("ml", ["llms", "large language models", "generative ai"]),
    "pandas": ("data", []),
    "numpy": ("data", []),
    "data analysis": ("data", ["data analytics"]),
    "data visualization": ("data", ["data visualisation"]),
    "tableau": ("data", []),
    "power bi": ("data", ["powerbi"]),
    "excel": ("data", ["ms excel", "advanced excel"]),
    "statistics": ("data", ["statistical analysis"]),
    "spark": ("data", ["pyspark", "apache spark"]),
    "hadoop": ("data", []),
    # mobile
    "android": ("mobile", []),
    "ios": ("mobile", []),
    "flutter": ("mobile", []),
    "react native": ("mobile", []),
    # CS fundamentals
    "data structures": ("cs", ["dsa"]),
    "algorithms": ("cs", ["algorithm design"]),
    "oop": ("cs", ["object oriented programming", "object-oriented programming", "object oriented"]),
    "operating systems": ("cs", ["os concepts"]),
    "computer networks": ("cs", ["networking"]),
    # testing / tools
    "unit testing": ("tools", ["junit", "pytest"]),
    "selenium": ("tools", []),
    "postman": ("tools", []),
    "jira": ("tools", []),
    "figma": ("design", []),
    # core engineering / electronics
    "embedded systems": ("embedded", ["embedded c", "embedded software"]),
    "arduino": ("embedded", []),
    "iot": ("embedded", ["internet of things"]),
    "raspberry pi": ("embedded", []),
    "vlsi": ("embedded", ["verilog", "vhdl"]),
    "plc": ("embedded", ["scada"]),
    "autocad": ("mechanical", []),
    "solidworks": ("mechanical", []),
    "catia": ("mechanical", []),
    "ansys": ("mechanical", []),
    "cad": ("mechanical", ["cad design"]),
}

CATEGORY = {k: v[0] for k, v in SKILL_TAXONOMY.items()}
ALIAS_TO_CANON = {}
for _canon, (_cat, _aliases) in SKILL_TAXONOMY.items():
    ALIAS_TO_CANON[_canon] = _canon
    for _a in _aliases:
        ALIAS_TO_CANON[_a] = _canon


def _build_patterns():
    pats = {}
    for canon, (_cat, aliases) in SKILL_TAXONOMY.items():
        names = sorted({canon, *aliases}, key=len, reverse=True)
        body = "|".join(re.escape(n).replace(r"\ ", r"[\s\-]+") for n in names)
        pats[canon] = re.compile(r"(?<![\w+#.])(?:" + body + r")(?![\w+#])", re.IGNORECASE)
    return pats


_PATTERNS = _build_patterns()
_BARE_AMBIGUOUS = {"c", "r", "go"}

STOPWORDS = set(
    "a an the and or of to in for on with at by from as is are was were be been being this that these those it its "
    "we you your our they their i my me he she his her will can should would could may might must have has had do "
    "does did not no yes if then than so such into about over under per etc using use used work working worked "
    "experience experienced strong good great ability able knowledge understanding looking role candidate candidates "
    "team teams company across including within across also more most other any all each new".split()
)

SECTION_PATTERNS = {
    "education": r"\b(education|academic|qualification|b\.?\s?tech|b\.?\s?e\b|bachelor|cgpa|gpa)\b",
    "experience": r"\b(experience|internship|intern|employment|work history)\b",
    "projects": r"\b(projects?|capstone|hackathon)\b",
    "skills": r"\b(skills|technologies|tech stack|tools)\b",
}


def normalize_skill(s):
    s = re.sub(r"\s+", " ", str(s).strip().lower())
    return ALIAS_TO_CANON.get(s, s)


def extract_skills(text):
    """Return canonical skills mentioned in free text (taxonomy based)."""
    if not text:
        return []
    found = []
    for canon, pat in _PATTERNS.items():
        for m in pat.finditer(text):
            token = m.group(0).lower()
            # bare "c", "r", "go" are far too common as plain words/letters; require the long forms
            if canon in _BARE_AMBIGUOUS and token == canon:
                continue
            found.append(canon)
            break
    return found


def tokenize(text):
    words = re.findall(r"[a-z][a-z0-9+#]*", (text or "").lower())
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def build_idf(docs):
    """Smoothed inverse document frequency over a list of raw-text documents."""
    n = len(docs)
    df = Counter()
    for d in docs:
        df.update(set(tokenize(d)))
    return {w: math.log((1 + n) / (1 + c)) + 1.0 for w, c in df.items()}


def tfidf_cosine(a, b, idf=None):
    ta, tb = Counter(tokenize(a)), Counter(tokenize(b))
    if not ta or not tb:
        return 0.0
    idf = idf or build_idf([a, b])
    default = max(idf.values()) if idf else 1.0
    va = {w: c * idf.get(w, default) for w, c in ta.items()}
    vb = {w: c * idf.get(w, default) for w, c in tb.items()}
    dot = sum(v * vb.get(w, 0.0) for w, v in va.items())
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    return dot / (na * nb) if na and nb else 0.0


def _unique(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def verdict(score):
    if score >= 75:
        return "Strong match"
    if score >= 55:
        return "Good match"
    if score >= 35:
        return "Partial match"
    return "Low match"


def score_match(resume_text, profile_skills, job, idf=None, cgpa=None):
    """Score one candidate against one job. `job` needs title/description/skills/min_cgpa."""
    have = set(normalize_skill(s) for s in (profile_skills or [])) | set(extract_skills(resume_text))
    job_text = f"{job.get('title', '')} {job.get('description', '')} {' '.join(job.get('skills') or [])}"
    desc_skills = extract_skills(job_text)
    required = _unique(normalize_skill(s) for s in (job.get("skills") or []))
    if not required:
        required = desc_skills
    preferred = [s for s in desc_skills if s not in required]

    matched, related, missing, credit = [], [], [], 0.0
    for s in required:
        if s in have:
            matched.append(s)
            credit += 1.0
            continue
        cat = CATEGORY.get(s)
        via = sorted(h for h in have if cat and CATEGORY.get(h) == cat and h != s)
        if via:
            related.append({"skill": s, "via": via[:2]})
            credit += 0.3
        else:
            missing.append(s)

    skill_score = credit / len(required) if required else None
    raw_cos = tfidf_cosine(resume_text or "", job_text, idf)
    text_score = min(1.0, raw_cos / 0.35)  # resume-vs-JD cosine rarely exceeds ~0.4

    min_cgpa = float(job.get("min_cgpa") or 0)
    if cgpa is None:
        academic = 0.5
    else:
        academic = max(0.0, min(1.0, 0.4 + 0.6 * (float(cgpa) - min_cgpa) / max(10.0 - min_cgpa, 1.0)))

    if skill_score is None:
        final = 0.85 * text_score + 0.15 * academic
    else:
        final = 0.65 * skill_score + 0.25 * text_score + 0.10 * academic
    if not (resume_text or "").strip() and not have:
        final *= 0.5
    score = int(round(max(0.0, min(1.0, final)) * 100))

    tips = []
    if missing:
        tips.append("Learn or showcase: " + ", ".join(missing[:4]) + ".")
    if related:
        tips.append("You have related skills for " + ", ".join(r["skill"] for r in related[:3]) +
                    "; mention transferable project work.")
    if text_score < 0.35 and (resume_text or "").strip():
        tips.append("Mirror the job description's keywords in your project and experience bullets.")

    return {
        "score": score,
        "verdict": verdict(score),
        "breakdown": {
            "skills": None if skill_score is None else int(round(skill_score * 100)),
            "text": int(round(text_score * 100)),
            "academic": int(round(academic * 100)),
        },
        "matched": matched,
        "related": related,
        "missing": missing,
        "preferred_matched": [s for s in preferred if s in have],
        "tips": tips,
    }


def analyze_resume(text):
    """Heuristic resume quality check: detected skills, sections, score out of 100 and tips."""
    text = text or ""
    words = len(re.findall(r"\S+", text))
    skills = extract_skills(text)
    by_cat = {}
    for s in skills:
        by_cat.setdefault(CATEGORY.get(s, "other"), []).append(s)

    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
    has_phone = bool(re.search(r"(\+?\d[\d\s\-()]{8,}\d)", text))
    sections = {name: bool(re.search(p, text, re.IGNORECASE)) for name, p in SECTION_PATTERNS.items()}
    quantified = len(re.findall(r"\d+\s?%|\b\d{2,}\+?\b|\bx\d\b", text))
    action_verbs = len(re.findall(
        r"\b(built|developed|designed|implemented|led|created|optimi[sz]ed|reduced|improved|deployed|automated|"
        r"launched|analy[sz]ed|managed|engineered)\b", text, re.IGNORECASE))

    checks = [
        ("Email address", 10, has_email, "Add a professional email address."),
        ("Phone number", 5, has_phone, "Add a phone number recruiters can call."),
        ("Education section", 15, sections["education"], "Add an Education section with degree and CGPA."),
        ("Experience / internships", 15, sections["experience"], "Add internships or work experience, even short ones."),
        ("Projects section", 15, sections["projects"], "Add 2-3 projects with the tech stack you used."),
        ("Skills section", 10, sections["skills"], "Add a dedicated Skills section."),
        ("5+ recognised skills", 10, len(skills) >= 5, "List more concrete technologies (aim for 8+)."),
        ("Quantified achievements", 10, quantified >= 3 and action_verbs >= 2,
         "Use action verbs and numbers: 'Reduced API latency by 35%'."),
        ("Good length (150-700 words)", 10, 150 <= words <= 700,
         "Aim for one page: 150-700 words."),
    ]
    score = sum(w for _n, w, ok, _t in checks if ok)
    return {
        "score": score,
        "word_count": words,
        "skills": skills,
        "skills_by_category": by_cat,
        "sections": sections,
        "checks": [{"name": n, "points": w, "passed": ok} for n, w, ok, _t in checks],
        "tips": [t for _n, _w, ok, t in checks if not ok],
    }
