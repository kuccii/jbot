from abc import ABC, abstractmethod

from job_bot.discovery.base import Opportunity


class ATSProvider(ABC):
    name: str = ""

    @abstractmethod
    async def fetch_jobs(self, companies: list[str] | None = None) -> list[Opportunity]:
        ...

    @abstractmethod
    async def check_live(self, url: str) -> bool:
        ...
