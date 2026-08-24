import pytest
from job_bot.intelligence.analysis.matcher import Matcher, FALLBACK_SCORES


class MockProvider:
    def __init__(self, response: str):
        self._response = response

    async def generate(self, prompt: str, system: str | None = None) -> str:
        return self._response


class TestMultiDimScoring:
    @pytest.mark.asyncio
    async def test_valid_json_response(self):
        mock = MockProvider('{"cv_match": 85, "compensation": 60, "culture": 70, "red_flags": 90, "legitimacy": 80, "global": 75, "prose": "Good fit for this role"}')
        matcher = Matcher(mock)
        scores = await matcher.score("Profile", "Job posting")
        assert scores["cv_match"] == 85
        assert scores["composite"] == 76

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        mock = MockProvider("not json at all")
        matcher = Matcher(mock)
        scores = await matcher.score("Profile", "Job")
        assert scores["composite"] == 50
        assert scores["cv_match"] == 50

    @pytest.mark.asyncio
    async def test_partial_json_fallback(self):
        mock = MockProvider('{"cv_match": 85}')
        matcher = Matcher(mock)
        scores = await matcher.score("Profile", "Job")
        assert scores["composite"] == 50

    @pytest.mark.asyncio
    async def test_score_clamping(self):
        mock = MockProvider('{"cv_match": 999, "compensation": -5, "culture": 70, "red_flags": 90, "legitimacy": 80, "global": 75, "prose": "test"}')
        matcher = Matcher(mock)
        scores = await matcher.score("Profile", "Job")
        assert scores["cv_match"] == 100
        assert scores["compensation"] == 0

    @pytest.mark.asyncio
    async def test_fallback_scores_immutable(self):
        original = FALLBACK_SCORES["composite"]
        assert original == 50
