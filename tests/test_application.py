import pytest
from job_bot.application.registry import get_applier
from job_bot.application.manager import ApplicationManager


class TestApplication:
    def test_greenhouse_detection(self):
        applier = get_applier("https://boards.greenhouse.io/openai/jobs/123")
        assert applier is not None
        assert applier.name == "greenhouse"

    def test_lever_detection(self):
        applier = get_applier("https://jobs.lever.co/stripe/456")
        assert applier is not None
        assert applier.name == "lever"

    def test_unknown_url_falls_to_generic(self):
        applier = get_applier("https://example.com/careers")
        assert applier is not None
        assert applier.name == "generic"

    @pytest.mark.asyncio
    async def test_startup_returns_manual_submission(self):
        mgr = ApplicationManager()
        result = await mgr.submit("https://ycombinator.com/apply", {}, "cover", category="startup")
        assert result["success"] is True
        assert "manual submission" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_grant_returns_manual_submission(self):
        mgr = ApplicationManager()
        result = await mgr.submit("https://nsf.gov/apply", {}, "proposal", category="grant")
        assert result["success"] is True
        assert "manual submission" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_job_does_not_short_circuit(self):
        mgr = ApplicationManager()
        result = await mgr.submit("https://example.com/job", {}, "cover", category="job")
        assert result["success"] is False or "platform" in result
