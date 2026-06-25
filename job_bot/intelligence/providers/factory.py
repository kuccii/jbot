from job_bot.intelligence.providers.base import LLMProvider
from job_bot.intelligence.providers.ollama import OllamaProvider
from job_bot.intelligence.providers.gemini import GeminiProvider
from job_bot.intelligence.providers.nim import NimProvider
from job_bot.intelligence.providers.opencode import OpenCodeProvider


_PROVIDERS = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "nim": NimProvider,
    "opencode": OpenCodeProvider,
}


def create_provider(name: str, **kwargs) -> LLMProvider:
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Options: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[name](**kwargs)
