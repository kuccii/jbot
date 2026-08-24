from job_bot.discovery.base import SearchCriteria
from job_bot.discovery.registry import list_scrapers, get_scraper
from job_bot.discovery.utils import is_expired, is_rwanda_eligible
from job_bot.discovery.providers import ATS_PROVIDERS
from job_bot.discovery.aggregator_domains import AGGREGATOR_DOMAINS
from job_bot.database.repository import Repository
from job_bot.intelligence.web.client import WebClient
from job_bot.utils.logging import get_logger

logger = get_logger()


class DiscoveryOrchestrator:
    def __init__(self, repo: Repository, config: dict, web_services: dict | None = None):
        self.repo = repo
        self.config = config
        self._web_client = WebClient(web_services or {})

    async def run_all(self) -> list:
        criteria = SearchCriteria(
            skills=self.config.get("skills", []),
        )
        sources_config = self.config.get("sources", {})
        all_ops = []
        normalized_titles: set[str] = set()
        for name in list_scrapers():
            if not sources_config.get(name, True):
                continue
            try:
                scraper = get_scraper(name)
                if hasattr(scraper, "set_web_client"):
                    scraper.set_web_client(self._web_client)
                if name == "company_pages":
                    scraper.set_companies(self.config.get("companies", []))
                opps = await scraper.discover(criteria)
                for opp in opps:
                    opp_url = (opp.url or "").lower()
                    opp_company = (opp.company or "").lower()
                    if any(d in opp_url or d in opp_company for d in AGGREGATOR_DOMAINS):
                        continue
                    if not is_rwanda_eligible(opp.title, opp.company, opp.description, "", opp.remote):
                        continue
                    norm = opp.title.lower().strip()[:100]
                    if norm in normalized_titles:
                        continue
                    normalized_titles.add(norm)
                    if is_expired(opp.deadline):
                        continue
                    oid = self.repo.add_opportunity({
                        "title": opp.title,
                        "company": opp.company,
                        "url": opp.url,
                        "description": opp.description,
                        "source": opp.source,
                        "remote": opp.remote,
                        "category": opp.category,
                        "deadline": opp.deadline,
                    })
                    if oid:
                        all_ops.append(opp)
                logger.info("scraper_complete", scraper=name, count=len(opps))
            except Exception as e:
                logger.error("scraper_failed", scraper=name, error=str(e))

        # ATS providers
        for provider in ATS_PROVIDERS:
            try:
                opps = await provider.fetch_jobs()
                for opp in opps:
                    if not is_rwanda_eligible(opp.title, opp.company, opp.description, opp.location, opp.remote):
                        continue
                    norm = opp.title.lower().strip()[:100]
                    if norm in normalized_titles:
                        continue
                    normalized_titles.add(norm)
                    if is_expired(opp.deadline):
                        continue
                    oid = self.repo.add_opportunity({
                        "title": opp.title,
                        "company": opp.company,
                        "url": opp.url,
                        "description": opp.description,
                        "source": opp.source,
                        "remote": opp.remote,
                        "category": opp.category,
                        "deadline": opp.deadline,
                        "location": opp.location,
                    })
                    if oid:
                        all_ops.append(opp)
                logger.info("ats_provider_complete", provider=provider.name, count=len(opps))
            except Exception as e:
                logger.error("ats_provider_failed", provider=provider.name, error=str(e))

        return all_ops
