import pytest
from job_bot.discovery.registry import list_scrapers, get_scraper
from job_bot.discovery.base import SearchCriteria


class TestDiscovery:
    def test_registry_has_scrapers(self):
        scrapers = list_scrapers()
        assert len(scrapers) > 0
        assert "google_search" in scrapers
        assert "linkedin" in scrapers
        assert "company_pages" in scrapers
        assert "fuzu" in scrapers

    def test_all_scrapers_return_lists(self):
        criteria = SearchCriteria(skills=["Python"])
        for name in list_scrapers():
            scraper = get_scraper(name)
            assert hasattr(scraper, "discover")

    def test_orchestrator_creates(self, tmp_path):
        from job_bot.discovery.orchestrator import DiscoveryOrchestrator
        from job_bot.database.repository import init_db, Repository
        db_path = str(tmp_path / "test.db")
        db_url = init_db(db_path)
        repo = Repository(db_url)
        orch = DiscoveryOrchestrator(repo, {"skills": ["Python"]}, web_services={})
        assert orch._web_client is not None
