from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ApplicationResult:
    success: bool
    message: str = ""
    screenshot_path: str = ""
    platform: str = ""


class BaseApplier(ABC):
    name: str = ""
    url_patterns: list[str] = []

    @abstractmethod
    async def apply(self, url: str, profile: dict, cover_letter: str, answers: dict | None = None) -> ApplicationResult:
        ...
