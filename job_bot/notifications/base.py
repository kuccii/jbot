from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    @abstractmethod
    async def send_message(self, to: str, text: str) -> bool:
        ...

    @abstractmethod
    async def send_template(self, to: str, template_name: str, params: dict) -> bool:
        ...
