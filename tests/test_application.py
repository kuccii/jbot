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
    async def test_job_goes_through_applier(self):
        mgr = ApplicationManager()
        result = await mgr.submit("https://example.com/job", {}, "cover", category="job")
        assert "platform" in result

    @pytest.mark.asyncio
    async def test_job_with_config(self):
        mgr = ApplicationManager(config={"autonomous_apply": False, "web_services": {}})
        result = await mgr.submit("https://example.com/job", {}, "cover", category="job")
        assert "platform" in result
