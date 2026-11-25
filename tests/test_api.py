import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CAMPUSHIRE_QUIET"] = "1"
import server  # noqa: E402


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.srv = server.create_server(os.path.join(cls.tmp.name, "t.db"), "127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def call(self, method, path, body=None, token=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def login(self, email, pw):
        status, data = self.call("POST", "/api/login", {"email": email, "password": pw})
        self.assertEqual(status, 200, data)
        return data["token"]

    # ------------------------------------------------------------ auth
    def test_login_failures_and_me(self):
        self.assertEqual(self.call("POST", "/api/login", {"email": "aarav@campus.edu", "password": "nope"})[0], 401)
        self.assertEqual(self.call("GET", "/api/me")[0], 401)
        t = self.login("aarav@campus.edu", "student123")
        s, me = self.call("GET", "/api/me", token=t)
        self.assertEqual(me["user"]["role"], "student")
        self.assertGreater(me["profile"]["completeness"], 80)

    def test_register_validation_and_flow(self):
        base = {"name": "Test Kid", "email": "kid@campus.edu", "password": "secret1", "role": "student",
                "branch": "cse", "cgpa": 8, "grad_year": 2027}
        self.assertEqual(self.call("POST", "/api/register", dict(base, password="x"))[0], 400)
        self.assertEqual(self.call("POST", "/api/register", dict(base, role="admin"))[0], 400)
        self.assertEqual(self.call("POST", "/api/register", dict(base, cgpa=11))[0], 400)
        s, d = self.call("POST", "/api/register", base)
        self.assertEqual(s, 201, d)
        self.assertEqual(self.call("POST", "/api/register", base)[0], 409)
        # no resume yet -> cannot apply
        s, jobs = self.call("GET", "/api/jobs", token=d["token"])
        jid = next(j["id"] for j in jobs["jobs"] if j["title"] == "Full Stack Developer")
        s, r = self.call("POST", f"/api/jobs/{jid}/apply", token=d["token"])
        self.assertEqual(s, 400)
        self.assertIn("resume", r["error"].lower())
        # add resume + skills, then apply works
        s, r = self.call("PUT", "/api/profile", {
            "skills": "JavaScript, ReactJS, Node.js, HTML, CSS",
            "resume_text": "Built a React and Node.js shopping app with MongoDB. " * 3}, token=d["token"])
        self.assertEqual(s, 200, r)
        self.assertIn("react", r["profile"]["skills"])
        s, r = self.call("POST", f"/api/jobs/{jid}/apply", token=d["token"])
        self.assertEqual(s, 201, r)
        self.assertGreater(r["match_score"], 50)
        self.assertEqual(self.call("POST", f"/api/jobs/{jid}/apply", token=d["token"])[0], 409)

    # ------------------------------------------------------------ matching & eligibility
    def test_job_list_ranked_by_match_with_explanations(self):
        t = self.login("ananya@campus.edu", "student123")
        s, d = self.call("GET", "/api/jobs?sort=match", token=t)
        jobs = d["jobs"]
        self.assertEqual(jobs[0]["title"], "Machine Learning Engineer")
        scores = [j["match"]["score"] for j in jobs]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("pytorch", jobs[0]["match"]["matched"])
        self.assertTrue(jobs[0]["applied"])

    def test_ineligible_student_blocked(self):
        t = self.login("rohan@campus.edu", "student123")  # CGPA 7.4, IT
        s, d = self.call("GET", "/api/jobs", token=t)
        java = next(j for j in d["jobs"] if j["title"] == "Java Developer")  # min 7.5
        self.assertFalse(java["eligible"])
        s, r = self.call("POST", f"/api/jobs/{java['id']}/apply", token=t)
        self.assertEqual(s, 403)
        t2 = self.login("karan@campus.edu", "student123")  # MECH
        s, d = self.call("GET", "/api/jobs", token=t2)
        ml = next(j for j in d["jobs"] if j["title"] == "Machine Learning Engineer")
        self.assertFalse(ml["eligible"])

    # ------------------------------------------------------------ recruiter flow
    def test_recruiter_post_rank_and_update(self):
        rt = self.login("hr@nimbus.com", "recruit123")
        deadline = (date.today() + timedelta(days=5)).isoformat()
        bad = {"title": "X", "description": "short", "deadline": deadline}
        self.assertEqual(self.call("POST", "/api/jobs", bad, rt)[0], 400)
        self.assertEqual(self.call("POST", "/api/jobs", dict(bad, description="x" * 30, deadline="2000-01-01"), rt)[0], 400)
        s, job = self.call("POST", "/api/jobs", {
            "title": "SRE Intern", "description": "Keep services up with Kubernetes, Docker and Linux on AWS.",
            "min_cgpa": 6.5, "branches": ["CSE"], "package_lpa": 7, "deadline": deadline,
            "job_type": "Internship"}, rt)
        self.assertEqual(s, 201, job)
        self.assertIn("kubernetes", job["skills"])  # auto-extracted from description
        # a student can't post jobs
        st = self.login("aarav@campus.edu", "student123")
        self.assertEqual(self.call("POST", "/api/jobs", {}, st)[0], 403)
        # aarav applies; recruiter sees applicants ranked and moves status
        self.assertEqual(self.call("POST", f"/api/jobs/{job['id']}/apply", token=st)[0], 201)
        pt = self.login("priya@campus.edu", "student123")
        self.assertEqual(self.call("POST", f"/api/jobs/{job['id']}/apply", token=pt)[0], 201)
        s, d = self.call("GET", f"/api/jobs/{job['id']}/applicants", token=rt)
        self.assertEqual(len(d["applicants"]), 2)
        scores = [a["match"]["score"] for a in d["applicants"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        aid = d["applicants"][0]["id"]
        self.assertEqual(self.call("PUT", f"/api/applications/{aid}/status", {"status": "bogus"}, rt)[0], 400)
        self.assertEqual(self.call("PUT", f"/api/applications/{aid}/status", {"status": "shortlisted"}, rt)[0], 200)
        # another recruiter cannot touch it
        other = self.login("talent@pixelco.com", "recruit123")
        self.assertEqual(self.call("GET", f"/api/jobs/{job['id']}/applicants", token=other)[0], 403)
        self.assertEqual(self.call("PUT", f"/api/applications/{aid}/status", {"status": "offered"}, other)[0], 403)
        # closing the job blocks new applications
        self.assertEqual(self.call("PUT", f"/api/jobs/{job['id']}/status", {"status": "closed"}, rt)[0], 200)
        s, d = self.call("GET", "/api/jobs", token=self.login("ananya@campus.edu", "student123"))
        self.assertNotIn(job["id"], [j["id"] for j in d["jobs"]])

    def test_withdraw_only_before_review(self):
        t = self.login("aarav@campus.edu", "student123")
        s, d = self.call("GET", "/api/applications", token=t)
        reviewed = next(a for a in d["applications"] if a["status"] == "shortlisted")
        self.assertEqual(self.call("DELETE", f"/api/applications/{reviewed['id']}", token=t)[0], 400)

    # ------------------------------------------------------------ admin & tools
    def test_admin_stats_and_access(self):
        self.assertEqual(self.call("GET", "/api/admin/stats", token=self.login("aarav@campus.edu", "student123"))[0], 403)
        s, d = self.call("GET", "/api/admin/stats", token=self.login("admin@campushire.edu", "admin123"))
        self.assertEqual(s, 200)
        self.assertGreaterEqual(d["students"], 6)
        self.assertGreaterEqual(d["placed_students"], 2)
        self.assertEqual(sum(b["students"] for b in d["branches"]), d["students"])
        self.assertTrue(0 <= d["placement_rate"] <= 100)

    def test_resume_analyzer_and_skill_extractor(self):
        t = self.login("aarav@campus.edu", "student123")
        s, d = self.call("POST", "/api/resume/analyze", {"text": "Skills: Python, Django, Docker"}, t)
        self.assertEqual(s, 200)
        self.assertIn("django", d["skills"])
        self.assertEqual(self.call("POST", "/api/resume/analyze", {"text": "  "}, t)[0], 400)
        s, d = self.call("POST", "/api/skills/extract", {"text": "We use React and Postgres"}, t)
        self.assertEqual(set(d["skills"]), {"react", "postgresql"})

    def test_static_and_unknown_routes(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertEqual(r.status, 200)
        self.assertEqual(self.call("GET", "/api/nope", token=None)[0], 404)
        self.assertEqual(self.call("DELETE", "/api/login")[0], 405)
        with urllib.request.urlopen(self.base + "/..%2f..%2fetc/passwd") as r:  # traversal falls back to SPA
            self.assertIn(b"CampusHire", r.read())


if __name__ == "__main__":
    unittest.main()
