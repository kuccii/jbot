"""Board base class."""

from abc import ABC, abstractmethod

import httpx

from job_hunter.fetch import DEFAULT_HEADERS
from job_hunter.models import Job


class Board(ABC):
    name: str = ""
    label: str = ""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    def client(self) -> httpx.AsyncClient:
        """Get a clean async httpx client. No proxy injection."""
        kwargs: dict = {"headers": DEFAULT_HEADERS, "timeout": 15.0}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    @abstractmethod
    async def fetch(self, limit: int = 30) -> list[Job]:
        """Fetch job listings from this board."""
