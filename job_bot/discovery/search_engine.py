"""Base class for WebClient-powered search scrapers (replaces Serper)."""

from job_bot.discovery.base import BaseScraper


class SearchEngineScraper(BaseScraper):
    """Base scraper that uses WebClient.search() for web search."""

    def __init__(self):
        self._web_client = None

    def set_web_client(self, client):
        self._web_client = client

    async def _search(self, q: str) -> list[dict]:
        if not self._web_client:
            return []
        try:
            results = await self._web_client.search(q, limit=10)
            normalized = []
            for r in results:
                normalized.append({
                    "title": r.get("title", ""),
                    "link": r.get("url", r.get("link", "")),
                    "snippet": r.get("description", r.get("snippet", "")),
                    "source": r.get("source", ""),
                })
            return normalized
        except Exception:
            return []
