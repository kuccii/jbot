import re

import httpx
from bs4 import BeautifulSoup

from job_bot.discovery.providers.greenhouse import GreenhouseProvider
from job_bot.discovery.providers.lever import LeverProvider
from job_bot.discovery.providers.ashby import AshbyProvider
from job_bot.utils.logging import get_logger

logger = get_logger()

LIVENESS_PROVIDERS = [
    (re.compile(r"boards\.greenhouse\.io/.*/jobs/\d+"), GreenhouseProvider()),
    (re.compile(r"jobs\.lever\.co/[^/]+/[^/]+"), LeverProvider()),
    (re.compile(r"jobs\.ashbyhq\.com/[^/]+"), AshbyProvider()),
]

DEAD_PHRASES = [
    "no longer accepting", "position has been filled",
    "this posting is no longer", "job has been removed",
    "page not found", "this job is no longer",
    "we are no longer accepting applications",
    "this position has been filled",
]


class LivenessChecker:
    def __init__(self):
        self._http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

    async def check(self, url: str) -> tuple[bool, str]:
        for pattern, provider in LIVENESS_PROVIDERS:
            if pattern.search(url):
                is_live = await provider.check_live(url)
                return is_live, "ats_api"
        try:
            resp = await self._http_client.get(url)
            if resp.status_code in (404, 410):
                return False, "http_status"
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                text = soup.get_text(separator=" ", strip=True)[:2000].lower()
                if any(p in text for p in DEAD_PHRASES):
                    return False, "content_classifier"
                return True, "http_ok"
        except Exception:
            pass
        return True, "unknown"
