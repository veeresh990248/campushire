"""Demo data for CampusHire. Run `python seed.py` or let server.py seed an empty database."""
import json
from datetime import date, timedelta

import auth
import db as dbm
import matcher

STUDENT_PW = "student123"
RECRUITER_PW = "recruit123"
ADMIN_PW = "admin123"

STUDENTS = [
    ("Aarav Sharma", "aarav@campus.edu", "CSE", 8.7, 2027, "9876500001",
     ["python", "django", "react", "postgresql", "docker", "git"],
     """Aarav Sharma | aarav@campus.edu | +91 98765 00001
EDUCATION
B.Tech Computer Science, CGPA 8.7 (2023-2027)
EXPERIENCE
Backend Intern, Zoomline - Built REST APIs with Django and PostgreSQL, reduced query time by 40%. Deployed services with Docker.
PROJECTS
CampusConnect - Developed a Django + React student community platform used by 1200 students.
Expense Tracker - Designed a REST API with authentication, CI/CD using GitHub Actions.
SKILLS
Python, Django, React, PostgreSQL, Docker, Git, Data Structures, Algorithms, REST API, Linux"""),
    ("Priya Nair", "priya@campus.edu", "CSE", 9.1, 2027, "9876500002",
     ["java", "spring boot", "mysql", "aws", "microservices"],
     """Priya Nair | priya@campus.edu | +91 98765 00002
EDUCATION
B.Tech Computer Science, CGPA 9.1
EXPERIENCE
Software Intern, FinServe - Implemented microservices in Spring Boot with MySQL, improved throughput by 30%.
PROJECTS
Bank Ledger - Built a Java Spring Boot microservice with JWT auth and REST API, deployed on AWS EC2.
Library System - Designed an OOP based system with MySQL.
SKILLS
Java, Spring Boot, MySQL, AWS, Microservices, REST API, Data Structures, Algorithms, OOP, Git"""),
    ("Rohan Mehta", "rohan@campus.edu", "IT", 7.4, 2027, "9876500003",
     ["javascript", "node.js", "mongodb", "react", "html", "css"],
     """Rohan Mehta | rohan@campus.edu | +91 98765 00003
EDUCATION
B.Tech Information Technology, CGPA 7.4
PROJECTS
ShopSmart - Developed a MERN stack e-commerce site with 50+ products and payments.
Chat App - Created a realtime chat using Node.js, Express and MongoDB.
SKILLS
JavaScript, Node.js, Express, MongoDB, React, HTML, CSS, Git"""),
    ("Sneha Iyer", "sneha@campus.edu", "ECE", 8.2, 2027, "9876500004",
     ["c", "c++", "embedded systems", "arduino", "iot", "matlab"],
     """Sneha Iyer | sneha@campus.edu | +91 98765 00004
EDUCATION
B.Tech Electronics and Communication, CGPA 8.2
EXPERIENCE
Embedded Intern, Sensora Labs - Programmed ARM microcontrollers using embedded C, reduced power usage by 18%.
PROJECTS
Smart Irrigation - Built an IoT system with Arduino and sensors, deployed in 3 farms.
Signal Filter - Implemented FIR filters in MATLAB.
SKILLS
C programming, C++, Embedded Systems, Arduino, IoT, MATLAB, Raspberry Pi"""),
    ("Karan Patel", "karan@campus.edu", "MECH", 7.8, 2027, "9876500005",
     ["autocad", "solidworks", "matlab"],
     """Karan Patel | karan@campus.edu | +91 98765 00005
EDUCATION
B.Tech Mechanical Engineering, CGPA 7.8
PROJECTS
Go-kart chassis - Designed the chassis in SolidWorks and ran stress analysis in ANSYS.
Gear train - Drafted 2D drawings in AutoCAD.
SKILLS
AutoCAD, SolidWorks, ANSYS, MATLAB"""),
    ("Ananya Gupta", "ananya@campus.edu", "CSE", 8.9, 2027, "9876500006",
     ["python", "machine learning", "pytorch", "pandas", "numpy", "nlp", "sql"],
     """Ananya Gupta | ananya@campus.edu | +91 98765 00006
EDUCATION
B.Tech Computer Science, CGPA 8.9
EXPERIENCE
ML Intern, Vectorly - Trained NLP models with PyTorch, improved F1 score by 12%. Analyzed 2M rows with Pandas and SQL.
PROJECTS
Fake News Detector - Developed a transformer based NLP classifier reaching 94% accuracy.
Sales Forecasting - Built a machine learning pipeline with scikit-learn, NumPy and Pandas.
SKILLS
Python, Machine Learning, Deep Learning, PyTorch, Pandas, NumPy, NLP, SQL, Statistics, Git"""),
]

RECRUITERS = [
    ("Neha Kapoor", "hr@nimbus.com", "Nimbus Cloud"),
    ("Vikram Rao", "talent@pixelco.com", "Pixel & Co"),
    ("Sunita Rao", "campus@finedge.com", "FinEdge Bank"),
    ("Dev Malhotra", "jobs@cortex.ai", "Cortex AI"),
    ("Asha Menon", "hiring@voltix.com", "Voltix Embedded"),
    ("Rajesh Kumar", "careers@torque.com", "Torque Motors"),
]

# (recruiter email, title, description, skills, min_cgpa, branches, lpa, location, type, days_until_deadline)
JOBS = [
    ("hr@nimbus.com", "Backend Engineer",
     "Build scalable backend services in Python and Django backed by PostgreSQL. You will design REST APIs, "
     "containerise services with Docker and work with a small, fast moving platform team.",
     ["python", "django", "postgresql", "docker", "rest api"], 7.0, ["CSE", "IT"], 12, "Bengaluru", "Full-time", 20),
    ("hr@nimbus.com", "DevOps Engineer",
     "Own our CI/CD pipelines and cloud infrastructure. Work with Docker, Kubernetes, Terraform and AWS to keep "
     "services reliable. Comfortable with Linux and shell scripting.",
     ["docker", "kubernetes", "aws", "linux", "ci/cd", "terraform"], 7.0, ["CSE", "IT", "ECE"], 14, "Bengaluru", "Full-time", 25),
    ("talent@pixelco.com", "Full Stack Developer",
     "Ship features end to end across a React frontend and a Node.js and MongoDB backend. Great fit for people who "
     "love building products and have JavaScript projects to show.",
     ["javascript", "react", "node.js", "mongodb", "html", "css"], 6.5, ["CSE", "IT", "ECE"], 8, "Remote", "Full-time", 15),
    ("talent@pixelco.com", "Data Analyst Intern",
     "Analyse product and campaign data, build dashboards and share insights with marketing. Strong SQL and Excel "
     "needed; Tableau or Python is a plus. Internship with PPO.",
     ["sql", "excel", "tableau", "python", "statistics"], 6.0, [], 6.5, "Mumbai", "Internship + PPO", 10),
    ("campus@finedge.com", "Java Developer",
     "Develop banking microservices using Java and Spring Boot with MySQL. Solid understanding of OOP, data "
     "structures and REST API design expected.",
     ["java", "spring boot", "mysql", "microservices", "rest api"], 7.5, ["CSE", "IT"], 10, "Pune", "Full-time", 30),
    ("jobs@cortex.ai", "Machine Learning Engineer",
     "Train and ship NLP and deep learning models in production. You will work with PyTorch, Pandas and Python on "
     "large text datasets and own experiments from idea to deployment.",
     ["python", "machine learning", "pytorch", "pandas", "nlp"], 8.0, ["CSE", "IT"], 18, "Hyderabad", "Full-time", 18),
    ("hiring@voltix.com", "Embedded Software Engineer",
     "Write firmware in C and C++ for IoT devices and microcontrollers. Debug hardware with oscilloscopes and work "
     "closely with the electronics team on embedded systems.",
     ["c", "c++", "embedded systems", "iot"], 7.0, ["ECE", "EEE"], 9, "Chennai", "Full-time", 22),
    ("careers@torque.com", "Design Engineer",
     "Design vehicle components in SolidWorks and AutoCAD, run simulations and support prototyping on the shop floor.",
     ["solidworks", "autocad", "ansys"], 7.0, ["MECH"], 7, "Pune", "Full-time", 28),
]

# (student email, job title, status)
APPLICATIONS = [
    ("aarav@campus.edu", "Backend Engineer", "shortlisted"),
    ("aarav@campus.edu", "Full Stack Developer", "applied"),
    ("priya@campus.edu", "Java Developer", "offered"),
    ("priya@campus.edu", "Backend Engineer", "interview"),
    ("rohan@campus.edu", "Full Stack Developer", "interview"),
    ("sneha@campus.edu", "Embedded Software Engineer", "offered"),
    ("ananya@campus.edu", "Machine Learning Engineer", "shortlisted"),
    ("ananya@campus.edu", "Data Analyst Intern", "applied"),
    ("karan@campus.edu", "Design Engineer", "applied"),
]


def seed(conn):
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return False
    today = date.today()

    def add_user(name, email, pw, role):
        h, s = auth.hash_password(pw)
        return conn.execute(
            "INSERT INTO users (name,email,pw_hash,salt,role) VALUES (?,?,?,?,?)", (name, email, h, s, role)
        ).lastrowid

    add_user("TPO Admin", "admin@campushire.edu", ADMIN_PW, "admin")
    students = {}
    for name, email, branch, cgpa, yr, phone, skills, resume in STUDENTS:
        uid = add_user(name, email, STUDENT_PW, "student")
        conn.execute(
            "INSERT INTO students (user_id,branch,cgpa,grad_year,phone,skills,resume_text) VALUES (?,?,?,?,?,?,?)",
            (uid, branch, cgpa, yr, phone, json.dumps(skills), resume))
        students[email] = (uid, skills, resume, cgpa)
    recruiters = {}
    for name, email, company in RECRUITERS:
        uid = add_user(name, email, RECRUITER_PW, "recruiter")
        conn.execute("INSERT INTO companies (user_id,company_name) VALUES (?,?)", (uid, company))
        recruiters[email] = (uid, company)
    jobs = {}
    for rec_email, title, desc, skills, cg, branches, lpa, loc, jtype, days in JOBS:
        uid, company = recruiters[rec_email]
        jid = conn.execute(
            "INSERT INTO jobs (recruiter_id,title,company,description,skills,min_cgpa,branches,package_lpa,location,"
            "job_type,deadline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (uid, title, company, desc, json.dumps(skills), cg, json.dumps(branches), lpa, loc, jtype,
             (today + timedelta(days=days)).isoformat())).lastrowid
        jobs[title] = dict(id=jid, title=title, description=desc, skills=skills, min_cgpa=cg)
    for email, title, status in APPLICATIONS:
        uid, skills, resume, cgpa = students[email]
        job = jobs[title]
        m = matcher.score_match(resume, skills, job, cgpa=cgpa)
        conn.execute("INSERT INTO applications (job_id,student_id,status,match_score) VALUES (?,?,?,?)",
                     (job["id"], uid, status, m["score"]))
    conn.commit()
    return True


if __name__ == "__main__":
    import os
    path = os.environ.get("CAMPUSHIRE_DB", "campushire.db")
    dbm.init_db(path)
    c = dbm.connect(path)
    print("Seeded demo data." if seed(c) else "Database already has data; nothing seeded.")
    c.close()
