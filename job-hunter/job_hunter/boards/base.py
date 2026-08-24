"""Board base class."""

from abc import ABC, abstractmethod

import httpx

from job_hunter.fetch import DEFAULT_HEADERS, get_proxy_manager
from job_hunter.models import Job


class Board(ABC):
    name: str = ""
    label: str = ""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    def client(self) -> httpx.AsyncClient:
        kwargs: dict = {"headers": DEFAULT_HEADERS, "timeout": 15.0}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        # Auto-detect proxy from environment or config
        pm = get_proxy_manager()
        proxy_url = pm.get_proxy()
        if proxy_url and proxy_url not in ("managed:scraperapi", "managed:scrapingbee"):
            kwargs["proxy"] = proxy_url
        return httpx.AsyncClient(**kwargs)

    def client_proxied(self) -> httpx.AsyncClient:
        """Create a client that routes through a managed proxy (ScraperAPI/ScrapingBee).

        For boards that need JS rendering or Cloudflare bypass.
        """
        kwargs: dict = {"headers": DEFAULT_HEADERS, "timeout": 25.0}
        pm = get_proxy_manager()
        proxy_url = pm.get_proxy()
        if proxy_url and proxy_url not in ("managed:scraperapi", "managed:scrapingbee"):
            kwargs["proxy"] = proxy_url
        return httpx.AsyncClient(**kwargs)

    @abstractmethod
    async def fetch(self, limit: int = 30) -> list[Job]:
        """Fetch job listings from this board."""
