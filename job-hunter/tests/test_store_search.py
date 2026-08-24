import pytest
from job_hunter.models import Job, Store

@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))

def make_job(title="Python Engineer", company="Acme Remote", board="himalayas",
             url="https://himalayas.app/jobs/python-engineer", location="Worldwide", description=""):
    return Job(title=title, company=company, url=url, board=board,
               location=location, remote="Remote", description=description)

class TestGetJob:
    def test_returns_none_for_missing_id(self, store):
        assert store.get_job(999) is None
    def test_returns_row_for_existing_id(self, store):
        store.add_job(make_job(), True, "worldwide", score=42, score_reasons="skills: python")
        row = store.get_job(1)
        assert row is not None
        assert row["score"] == 42

class TestSearch:
    def test_matches_title(self, store):
        store.add_job(make_job(title="Senior Python Engineer"), True, "w")
        assert len(store.search("python")) == 1
    def test_no_match_returns_empty(self, store):
        store.add_job(make_job(), True, "w")
        assert store.search("kubernetes") == []
    def test_board_filter(self, store):
        store.add_job(make_job(board="himalayas"), True, "w")
        store.add_job(make_job(url="https://other.example/1", board="remotive"), True, "w")
        assert len(store.search("python", board="himalayas")) == 1
    def test_results_ordered_by_score_desc(self, store):
        store.add_job(make_job(title="Python Dev A"), True, "w", score=10)
        store.add_job(make_job(title="Python Dev B", url="https://other.example/1"), True, "w", score=90)
        results = store.search("python")
        assert [r["title"] for r in results] == ["Python Dev B", "Python Dev A"]

class TestNotificationTracking:
    def test_new_jobs_are_unnotified(self, store):
        store.add_job(make_job(), True, "w", score=50)
        assert len(store.unnotified()) == 1
    def test_mark_notified_excludes_from_future_queries(self, store):
        store.add_job(make_job(), True, "w", score=50)
        job_id = store.unnotified()[0]["id"]
        store.mark_notified([job_id])
        assert store.unnotified() == []

class TestSetScore:
    def test_updates_score_and_reasons(self, store):
        store.add_job(make_job(), True, "w")
        job_id = store.get_job(1)["id"]
        store.set_score(job_id, 77, "skills: python, django")
        row = store.get_job(job_id)
        assert row["score"] == 77
        assert row["score_reasons"] == "skills: python, django"
