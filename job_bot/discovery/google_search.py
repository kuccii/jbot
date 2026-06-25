import httpx
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("google_search")
class GoogleSearchScraper(BaseScraper):
    def __init__(self):
        self.api_key = ""

    def set_api_key(self, key: str):
        self.api_key = key

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self.api_key:
            return []
        async with httpx.AsyncClient() as client:
            results = []
            for keyword in criteria.keywords:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": f"{keyword} 1099 contract remote Africa 2026"},
                    headers={"X-API-KEY": self.api_key},
                )
                data = resp.json()
                for item in data.get("organic", []):
                    results.append(Opportunity(
                        title=item.get("title", ""),
                        company="",
                        url=item.get("link", ""),
                        description=item.get("snippet", ""),
                        source="google_search",
                        category="job",
                    ))
            return results
