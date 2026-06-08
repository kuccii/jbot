import pytest
from pathlib import Path
from job_bot.database.repository import init_db, Repository


class TestDatabase:
    @pytest.fixture
    def repo(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db_url = init_db(db_path)
        return Repository(db_url)

    def test_add_and_get_opportunity(self, repo):
        oid = repo.add_opportunity({
            "title": "AI Engineer",
            "company": "OpenAI",
            "url": "https://openai.com/careers/123",
            "source": "company_pages",
            "remote": "Remote",
        })
        assert oid > 0

    def test_no_duplicates(self, repo):
        oid1 = repo.add_opportunity({
            "title": "Duplicate",
            "company": "X",
            "url": "https://x.com/job/1",
        })
        oid2 = repo.add_opportunity({
            "title": "Duplicate",
            "company": "X",
            "url": "https://x.com/job/1",
        })
        assert oid1 == oid2

    def test_stats(self, repo):
        repo.add_opportunity({"title": "Job 1", "company": "A", "url": "https://a.com/1"})
        repo.add_opportunity({"title": "Job 2", "company": "B", "url": "https://b.com/1"})
        stats = repo.get_stats()
        assert stats["total"] == 2
        assert stats["new"] == 2

    def test_update_status(self, repo):
        oid = repo.add_opportunity({"title": "Job", "company": "C", "url": "https://c.com/1"})
        result = repo.update_opportunity_status(oid, "applied")
        assert result is True
        result_missing = repo.update_opportunity_status(999, "applied")
        assert result_missing is False

    def test_extra_keys_filtered(self, repo):
        oid = repo.add_opportunity({
            "title": "Job",
            "company": "C",
            "url": "https://c.com/job",
            "nonexistent_column": "should be ignored",
        })
        assert oid > 0

    def test_application_creation(self, repo):
        oid = repo.add_opportunity({"title": "Job", "company": "C", "url": "https://c.com/job"})
        app_id = repo.add_application({
            "opportunity_id": oid,
            "platform": "greenhouse",
            "status": "draft",
        })
        assert app_id > 0

    def test_audit_log(self, repo):
        repo.log_audit("test_action", "test_component", {"key": "value"})
