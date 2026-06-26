import pytest
from job_bot.discovery.providers.greenhouse import GreenhouseProvider
from job_bot.discovery.providers.lever import LeverProvider
from job_bot.discovery.providers.ashby import AshbyProvider


class TestProviders:
    def test_greenhouse_provider_initialization(self):
        p = GreenhouseProvider()
        assert p.name == "greenhouse"
        assert len(p.companies) > 0

    def test_lever_provider_initialization(self):
        p = LeverProvider()
        assert p.name == "lever"
        assert len(p.companies) > 0

    def test_ashby_provider_initialization(self):
        p = AshbyProvider()
        assert p.name == "ashby"
        assert len(p.companies) > 0

    def test_greenhouse_url_pattern(self):
        import re
        m = re.match(r"https://boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", "https://boards.greenhouse.io/openai/jobs/12345")
        assert m is not None
        assert m.group(1) == "openai"
        assert m.group(2) == "12345"

    def test_lever_url_pattern(self):
        import re
        m = re.match(r"https://jobs\.lever\.co/([^/]+)/([^/]+)", "https://jobs.lever.co/stripe/abc123")
        assert m is not None
        assert m.group(1) == "stripe"

    def test_ashby_url_pattern(self):
        import re
        m = re.match(r"https://jobs\.ashbyhq\.com/([^/]+)", "https://jobs.ashbyhq.com/linear")
        assert m is not None
        assert m.group(1) == "linear"
