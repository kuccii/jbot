"""Store tests — cross-board dedup and insert behavior (in-memory SQLite)."""

import pytest

from job_hunter.models import Job, Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


def make_job(title="Python Engineer", company="Acme Remote", board="himalayas",
             url="https://himalayas.app/jobs/python-engineer", location="Worldwide"):
    return Job(title=title, company=company, url=url, board=board,
               location=location, remote="Remote")


class TestAddJob:
    def test_new_job_inserts(self, store):
        assert store.add_job(make_job(), True, "worldwide") == "new"

    def test_same_url_returns_exists(self, store):
        store.add_job(make_job(), True, "worldwide")
        assert store.add_job(make_job(), True, "worldwide") == "exists"

    def test_cross_board_same_title_company_is_duplicate(self, store):
        store.add_job(make_job(), True, "worldwide")
        # Same role posted on another board with a different URL.
        other = make_job(url="https://remotive.com/remote-jobs/python-engineer",
                         board="remotive")
        assert store.add_job(other, True, "worldwide") == "duplicate"

    def test_title_punctuation_and_case_normalized(self, store):
        store.add_job(make_job(title="Senior, AI Engineer (Remote)"), True, "w")
        other = make_job(title="senior ai engineer remote",
                         url="https://other.example/1", board="jobicy")
        assert store.add_job(other, True, "w") == "duplicate"

    def test_different_title_same_company_is_new(self, store):
        store.add_job(make_job(title="Python Engineer"), True, "w")
        other = make_job(title="Data Scientist", url="https://other.example/1",
                         board="jobicy")
        assert store.add_job(other, True, "w") == "new"

    def test_different_company_same_title_is_new(self, store):
        store.add_job(make_job(company="Acme Remote"), True, "w")
        other = make_job(company="Other Co", url="https://other.example/1",
                         board="jobicy")
        assert store.add_job(other, True, "w") == "new"

    def test_empty_company_skips_cross_board_check(self, store):
        store.add_job(make_job(company="Acme"), True, "w")
        other = make_job(company="", url="https://other.example/1", board="jobicy")
        assert store.add_job(other, True, "w") == "new"
