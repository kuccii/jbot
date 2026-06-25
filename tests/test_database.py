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

    def test_opportunity_with_category(self, repo):
        oid = repo.add_opportunity({
            "title": "YC W26",
            "company": "Y Combinator",
            "url": "https://ycombinator.com/apply",
            "category": "startup",
            "program": "YC W26",
            "stage": "Pre-seed",
            "amount": "$500K",
        })
        assert oid > 0
        from job_bot.database.models import Opportunity
        from sqlalchemy.orm import Session
        with Session(repo.engine) as session:
            opp = session.query(Opportunity).filter_by(id=oid).first()
            assert opp.category == "startup"
            assert opp.program == "YC W26"
            assert opp.stage == "Pre-seed"
            assert opp.amount == "$500K"

    def test_audit_log(self, repo):
        repo.log_audit("test_action", "test_component", {"key": "value"})

    def test_get_pending_by_category(self, repo):
        repo.add_opportunity({"title": "Job 1", "company": "A", "url": "https://a.com/1", "category": "job"})
        repo.add_opportunity({"title": "Startup 1", "company": "YC", "url": "https://yc.com/1", "category": "startup"})
        repo.add_opportunity({"title": "Grant 1", "company": "NSF", "url": "https://nsf.gov/1", "category": "grant"})
        jobs = repo.get_pending_opportunities(category="job")
        assert len(jobs) == 1
        assert jobs[0].category == "job"
        stats = repo.get_stats_by_category()
        assert stats["job"] == 1
        assert stats["startup"] == 1
        assert stats["grant"] == 1
