import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import matcher  # noqa: E402

BACKEND_JOB = {
    "title": "Backend Engineer",
    "description": "Build REST APIs in Python and Django with PostgreSQL and Docker.",
    "skills": ["python", "django", "postgresql", "docker"],
    "min_cgpa": 7.0,
}
STRONG = "Built Django REST APIs in Python on PostgreSQL, deployed with Docker. Skills: Python, Django, PostgreSQL, Docker."
WEAK = "Designed gear trains in SolidWorks and AutoCAD. Skills: SolidWorks, AutoCAD, ANSYS."


class ExtractTests(unittest.TestCase):
    def test_extracts_known_skills_and_aliases(self):
        s = matcher.extract_skills("I use Postgres, k8s, ReactJS and Node.js daily; also C++ and C#.")
        for expected in ("postgresql", "kubernetes", "react", "node.js", "c++", "c#"):
            self.assertIn(expected, s)

    def test_java_is_not_javascript(self):
        self.assertEqual(matcher.extract_skills("Expert in JavaScript"), ["javascript"])
        self.assertIn("java", matcher.extract_skills("Java and JavaScript"))

    def test_sql_is_not_mysql_or_nosql(self):
        self.assertEqual(matcher.extract_skills("Used MySQL a lot"), ["mysql"])

    def test_bare_single_letters_ignored(self):
        self.assertEqual(matcher.extract_skills("Grade A, B, C and go home, R&D team"), [])
        self.assertIn("c", matcher.extract_skills("C programming and Golang"))
        self.assertIn("go", matcher.extract_skills("C programming and Golang"))

    def test_normalize(self):
        self.assertEqual(matcher.normalize_skill("  ReactJS "), "react")
        self.assertEqual(matcher.normalize_skill("Unknown Thing"), "unknown thing")


class ScoreTests(unittest.TestCase):
    def test_strong_beats_weak(self):
        strong = matcher.score_match(STRONG, [], BACKEND_JOB, cgpa=8.5)
        weak = matcher.score_match(WEAK, [], BACKEND_JOB, cgpa=8.5)
        self.assertGreater(strong["score"], 75)
        self.assertLess(weak["score"], 30)
        self.assertEqual(strong["missing"], [])
        self.assertEqual(set(weak["missing"]), {"python", "django", "postgresql", "docker"} - set(weak["related"] and []))

    def test_partial_credit_for_related_skill(self):
        job = dict(BACKEND_JOB, skills=["mysql"])
        r = matcher.score_match("Skills: PostgreSQL", [], job, cgpa=8)
        self.assertEqual(r["matched"], [])
        self.assertEqual(r["related"][0]["skill"], "mysql")
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["breakdown"]["skills"], 30)

    def test_profile_skills_count_without_resume_mention(self):
        r = matcher.score_match("short text", ["Python", "Django"], BACKEND_JOB, cgpa=8)
        self.assertEqual(set(r["matched"]), {"python", "django"})

    def test_higher_cgpa_helps(self):
        lo = matcher.score_match(STRONG, [], BACKEND_JOB, cgpa=7.0)
        hi = matcher.score_match(STRONG, [], BACKEND_JOB, cgpa=9.5)
        self.assertGreater(hi["score"], lo["score"])

    def test_scores_bounded_and_empty_resume_safe(self):
        r = matcher.score_match("", [], BACKEND_JOB)
        self.assertTrue(0 <= r["score"] <= 100)
        self.assertLess(r["score"], 30)

    def test_job_without_listed_skills_falls_back_to_description(self):
        job = dict(BACKEND_JOB, skills=[])
        r = matcher.score_match(STRONG, [], job, cgpa=8)
        self.assertIn("python", r["matched"])

    def test_verdict_bands(self):
        self.assertEqual(matcher.verdict(80), "Strong match")
        self.assertEqual(matcher.verdict(60), "Good match")
        self.assertEqual(matcher.verdict(40), "Partial match")
        self.assertEqual(matcher.verdict(10), "Low match")


class AnalyzeTests(unittest.TestCase):
    GOOD = """Jane Doe | jane@example.com | +91 98765 43210
EDUCATION B.Tech CSE, CGPA 8.5
EXPERIENCE Intern - Built APIs in Python, reduced latency by 35%, deployed 12 services and automated releases.
PROJECTS Developed a Django app with PostgreSQL and Docker serving 500 users. Implemented CI/CD.
SKILLS Python, Django, PostgreSQL, Docker, Git, Linux, React, SQL
""" + ("Built features and improved performance across several projects with measurable impact. " * 12)

    def test_good_resume_scores_high(self):
        a = matcher.analyze_resume(self.GOOD)
        self.assertGreaterEqual(a["score"], 85)
        self.assertIn("python", a["skills"])

    def test_empty_resume_scores_zero_with_tips(self):
        a = matcher.analyze_resume("hello")
        self.assertEqual(a["score"], 0)
        self.assertTrue(a["tips"])


class SimilarityTests(unittest.TestCase):
    def test_identical_is_one_and_disjoint_is_zero(self):
        self.assertAlmostEqual(matcher.tfidf_cosine("python django api", "python django api"), 1.0, places=5)
        self.assertEqual(matcher.tfidf_cosine("python django", "welding lathe"), 0.0)
        self.assertEqual(matcher.tfidf_cosine("", "anything"), 0.0)


if __name__ == "__main__":
    unittest.main()
