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
            seen = set()
            queries = []
            for skill in criteria.skills:
                queries.append(f"{skill} 1099 contract remote 2026")
                queries.append(f"hire {skill} freelance remote")
            for kw in criteria.keywords:
                queries.append(f"{kw} grant funding 2026")
            queries.append("remote contract developer Africa 2026")
            queries.append("remote AI engineer contract 2026")
            for q in queries:
                try:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        json={"q": q, "num": 10},
                        headers={"X-API-KEY": self.api_key},
                    )
                    data = resp.json()
                    for item in data.get("organic", []):
                        link = item.get("link", "")
                        if link not in seen:
                            seen.add(link)
                            results.append(Opportunity(
                                title=item.get("title", ""),
                                company=item.get("source", ""),
                                url=link,
                                description=item.get("snippet", ""),
                                source="google_search",
                                category="job",
                            ))
                except Exception:
                    pass
            return results
