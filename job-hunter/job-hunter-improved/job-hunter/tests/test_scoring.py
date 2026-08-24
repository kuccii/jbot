from job_hunter.models import Job
from job_hunter.scoring import score_job


def make_job(title="Software Engineer", description="", tags="", posted_at=""):
    return Job(title=title, company="Acme", url="https://example.com/1",
               board="himalayas", tags=tags, description=description,
               posted_at=posted_at)


class TestScoreJob:
    def test_no_skills_configured_gives_zero_and_says_so(self):
        score, reasons = score_job(make_job(), skills=[])
        assert score == 0
        assert "no profile skills matched" in reasons

    def test_title_match_scores_higher_than_description_match(self):
        title_hit, _ = score_job(make_job(title="Senior Python Engineer"), skills=["python"])
        desc_hit, _ = score_job(
            make_job(title="Senior Engineer", description="you'll write python daily"),
            skills=["python"],
        )
        assert title_hit > desc_hit

    def test_multiple_skill_matches_increase_score(self):
        job = make_job(title="Python Django Engineer", tags="react,postgres")
        one, _ = score_job(job, skills=["python"])
        many, _ = score_job(job, skills=["python", "django", "react", "postgres"])
        assert many > one

    def test_score_never_exceeds_100(self):
        job = make_job(
            title="Python Django React Postgres Kubernetes AWS Senior Engineer $150k USD",
            tags="python,django,react,postgres,kubernetes,aws",
        )
        score, _ = score_job(
            job, skills=["python", "django", "react", "postgres", "kubernetes", "aws"]
        )
        assert score <= 100

    def test_word_boundary_prevents_partial_matches(self):
        # "go" must not match "google" or "gopher" or "algorithm"
        score, reasons = score_job(make_job(title="Algorithm Engineer"), skills=["go"])
        assert score == 0

    def test_salary_mention_adds_points(self):
        base, _ = score_job(make_job(title="Python Engineer"), skills=["python"])
        with_salary, reasons = score_job(
            make_job(title="Python Engineer", description="salary range: $120k-150k USD"),
            skills=["python"],
        )
        assert with_salary > base
        assert "salary mentioned" in reasons

    def test_seniority_match_bonus(self):
        senior_job = make_job(title="Senior Python Engineer")
        matched, reasons = score_job(senior_job, skills=["python"], seniority="senior")
        unmatched, _ = score_job(senior_job, skills=["python"], seniority="")
        assert matched > unmatched
        assert "matches seniority" in reasons

    def test_seniority_mismatch_penalty(self):
        junior_job = make_job(title="Junior Python Engineer")
        senior_pref, reasons = score_job(junior_job, skills=["python"], seniority="senior")
        no_pref, _ = score_job(junior_job, skills=["python"], seniority="")
        assert senior_pref < no_pref
        assert "title looks junior" in reasons
