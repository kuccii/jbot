from job_bot.discovery.base import SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.aggregator_domains import AGGREGATOR_DOMAINS
from job_bot.discovery.search_engine import SearchEngineScraper

JOB_QUERIES = [
    "site:fuzu.com Python 2026",
    "site:fuzu.com software engineer remote 2026",
    "site:fuzu.com product manager 2026",
    "site:fuzu.com data science 2026",
    "site:remotejobsafrica.com remote 2026",
    "site:remotecareer.africa 2026",
    "site:remote4africa.com remote 2026",
    "site:remoteafrica.io 2026",
    "site:gebeya.com remote 2026",
    "site:tunga.io remote 2026",
    "site:opportunitiesforafricans.com 2026",
    "site:menterprise.africa 2026",
    "site:africanworkforce.com remote 2026",
    "site:jobberman.com remote 2026",
    "site:ethiojobs.net remote 2026",
]


@register("google_search")
class GoogleSearchScraper(SearchEngineScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self._web_client:
            return []
        results = []
        seen = set()
        for q in JOB_QUERIES:
            items = await self._search(q)
            for item in items:
                link = item.get("link", "")
                if link in seen:
                    continue
                seen.add(link)
                if any(d in link.lower() for d in AGGREGATOR_DOMAINS):
                    continue
                results.append(Opportunity(
                    title=item.get("title", ""),
                    company=item.get("source", ""),
                    url=link,
                    description=item.get("snippet", ""),
                    source="google_search",
                    category="job",
                ))
        return results
