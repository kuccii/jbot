from job_bot.discovery.base import SearchCriteria
from job_bot.discovery.registry import list_scrapers, get_scraper
from job_bot.database.repository import Repository
from job_bot.utils.logging import get_logger

logger = get_logger()


class DiscoveryOrchestrator:
    def __init__(self, repo: Repository, config: dict):
        self.repo = repo
        self.config = config

    async def run_all(self) -> list:
        criteria = SearchCriteria(
            skills=self.config.get("skills", []),
            keywords=self.config.get("grants_keywords", []),
        )
        all_ops = []
        for name in list_scrapers():
            try:
                scraper = get_scraper(name)
                if name == "google_search":
                    scraper.set_api_key(self.config.get("serper_api_key", ""))
                if name == "company_pages":
                    scraper.set_companies(self.config.get("companies", []))
                opps = await scraper.discover(criteria)
                for opp in opps:
                    oid = self.repo.add_opportunity({
                        "title": opp.title,
                        "company": opp.company,
                        "url": opp.url,
                        "description": opp.description,
                        "source": opp.source,
                        "remote": opp.remote,
                    })
                    if oid:
                        all_ops.append(opp)
                logger.info("scraper_complete", scraper=name, count=len(opps))
            except Exception as e:
                logger.error("scraper_failed", scraper=name, error=str(e))
        return all_ops
