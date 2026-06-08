from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchCriteria:
    skills: list[str] = field(default_factory=list)
    remote_only: bool = True
    job_types: list[str] = field(default_factory=lambda: ["contract", "freelance", "full-time"])
    locations: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class Opportunity:
    title: str
    company: str
    url: str
    description: str = ""
    source: str = ""
    deadline: datetime | None = None
    salary_range: str = ""
    location: str = ""
    remote: str = ""
    score: float = 0.0


class BaseScraper(ABC):
    name: str = ""

    @abstractmethod
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        ...
