from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = ""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...
