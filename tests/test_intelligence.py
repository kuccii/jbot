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


class MockProvider:
    def __init__(self, response: str = "50"):
        self.name = "mock"
        self._response = response

    async def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


class TestMatcher:
    def test_matcher_creation(self):
        provider = create_provider("ollama")
        matcher = Matcher(provider)
        assert matcher is not None

    @pytest.mark.asyncio
    async def test_score_job_prompt(self):
        matcher = Matcher(MockProvider("80"))
        result = await matcher.score("Profile", "Job opportunity", category="job")
        assert result == 0.8

    @pytest.mark.asyncio
    async def test_score_startup_prompt(self):
        matcher = Matcher(MockProvider("70"))
        result = await matcher.score("Profile", "Startup program", category="startup")
        assert result == 0.7

    @pytest.mark.asyncio
    async def test_score_grant_prompt(self):
        matcher = Matcher(MockProvider("90"))
        result = await matcher.score("Profile", "Grant opportunity", category="grant")
        assert result == 0.9

    @pytest.mark.asyncio
    async def test_score_fallback_to_job(self):
        matcher = Matcher(MockProvider("60"))
        result = await matcher.score("Profile", "Unknown", category="unknown")
        assert result == 0.6

    @pytest.mark.asyncio
    async def test_score_non_numeric_returns_zero(self):
        matcher = Matcher(MockProvider("not a number"))
        result = await matcher.score("Profile", "Job", category="job")
        assert result == 0.0


class TestDrafter:
    def test_drafter_creation(self):
        provider = create_provider("ollama")
        drafter = Drafter(provider)
        assert drafter is not None
