from job_bot.discovery.base import SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.search_engine import SearchEngineScraper

JOB_QUERIES = [
    "site:twitter.com remote jobs africa 2026",
    "site:twitter.com freelance remote developer worldwide",
    "site:twitter.com hiring remote developer global",
    "site:x.com remote jobs international africa",
    "site:twitter.com remote AI engineer worldwide",
    "site:twitter.com contract developer remote africa",
]


@register("twitter")
class TwitterScraper(SearchEngineScraper):
    def _is_valid_url(self, link: str) -> bool:
        return any(d in link.lower() for d in ("twitter.com", "x.com", "t.co"))

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self._web_client:
            return []
        results = []
        seen = set()
        job_qs = list(JOB_QUERIES)
        for skill in criteria.skills:
            job_qs.append(f"site:twitter.com {skill} freelance remote africa")
        for q in job_qs:
            items = await self._search(q)
            for item in items:
                link = item.get("link", "")
                if link in seen:
                    continue
                if not self._is_valid_url(link):
                    continue
                seen.add(link)
                results.append(Opportunity(
                    title=item.get("title", ""),
                    company=item.get("source", "Twitter"),
                    url=link,
                    description=item.get("snippet", ""),
                    source="twitter",
                    category="job",
                ))
        return results
