import httpx
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("twitter")
class TwitterScraper(BaseScraper):
    def __init__(self):
        self.api_key = ""

    def set_api_key(self, key: str):
        self.api_key = key

    def _categorize(self, title: str, snippet: str) -> str:
        text = (title + " " + snippet).lower()
        if any(w in text for w in ("grant", "funding", "fellowship", "scholarship")):
            return "grant"
        if any(w in text for w in ("startup", "accelerator", "incubator", "venture", "pitch")):
            return "startup"
        return "job"

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self.api_key:
            return []
        async with httpx.AsyncClient() as client:
            results = []
            seen = set()
            queries = []
            for skill in criteria.skills:
                queries.append(f"site:twitter.com {skill} freelance remote africa")
            queries.append("site:twitter.com developpp ventures funding 2026")
            queries.append("site:twitter.com giz rwanda tanzania jobs 2026")
            queries.append("site:twitter.com startup funding africa 2026")
            queries.append("site:twitter.com grant opportunity east africa")
            queries.append("site:x.com developpp ventures")
            queries.append("site:x.com giz africa opportunities")
            queries.append("site:twitter.com freelance remote developer africa")
            queries.append("site:twitter.com accelerator program africa 2026")
            queries.append("site:x.com rwanda tech funding")
            queries.append("site:twitter.com mastercard foundation fellowship")
            queries.append("site:twitter.com anzisha prize 2026")
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
                            snippet = item.get("snippet", "")
                            title = item.get("title", "")
                            results.append(Opportunity(
                                title=title,
                                company=item.get("source", "Twitter"),
                                url=link,
                                description=snippet,
                                source="twitter",
                                category=self._categorize(title, snippet),
                            ))
                except Exception:
                    pass
            return results
