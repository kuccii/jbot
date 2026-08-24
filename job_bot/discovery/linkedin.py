from job_bot.discovery.base import SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.search_engine import SearchEngineScraper

JOB_QUERIES = [
    "site:linkedin.com remote jobs worldwide africa",
    "site:linkedin.com freelance remote developer 2026",
    "site:linkedin.com remote developer contract global",
    "site:linkedin.com remote software engineer international",
    "site:linkedin.com remote product designer worldwide",
    "site:linkedin.com entry level remote jobs global",
    "site:linkedin.com freelance software engineer africa",
]


@register("linkedin")
class LinkedInScraper(SearchEngineScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self._web_client:
            return []
        results = []
        seen = set()
        job_qs = list(JOB_QUERIES)
        for skill in criteria.skills:
            job_qs.append(f"site:linkedin.com {skill} freelance remote 2026")
            job_qs.append(f"site:linkedin.com jobs {skill} contract")
        for q in job_qs:
            items = await self._search(q)
            for item in items:
                link = item.get("link", "")
                if link in seen:
                    continue
                seen.add(link)
                results.append(Opportunity(
                    title=item.get("title", ""),
                    company=item.get("source", "LinkedIn"),
                    url=link,
                    description=item.get("snippet", ""),
                    source="linkedin",
                    category="job",
                ))
        return results
