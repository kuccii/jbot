import pytest
from job_bot.intelligence.providers.factory import create_provider
from job_bot.intelligence.matcher import Matcher
from job_bot.intelligence.drafter import Drafter


class TestProviders:
    def test_factory_ollama(self):
        provider = create_provider("ollama", model="llama3.1:8b")
        assert provider.name == "ollama"

    def test_factory_gemini(self):
        provider = create_provider("gemini", api_key="test")
        assert provider.name == "gemini"

    def test_factory_invalid(self):
        with pytest.raises(ValueError):
            create_provider("invalid")


class TestMatcher:
    def test_matcher_creation(self):
        provider = create_provider("ollama")
        matcher = Matcher(provider)
        assert matcher is not None


class TestDrafter:
    def test_drafter_creation(self):
        provider = create_provider("ollama")
        drafter = Drafter(provider)
        assert drafter is not None
