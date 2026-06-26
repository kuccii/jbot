import re

import httpx

from job_bot.discovery.base import Opportunity
from job_bot.discovery.providers.base import ATSProvider

GREENHOUSE_BOARDS = {
    "openai": "openai",
    "stripe": "stripe",
    "airbnb": "airbnb",
    "gitlab": "gitlab",
    "notion": "notion",
    "vercel": "vercel",
    "datadog": "datadog",
    "hashicorp": "hashicorp",
    "deel": "deel",
    "canva": "canva",
}


class GreenhouseProvider(ATSProvider):
    name = "greenhouse"

    def __init__(self, companies: list[str] | None = None):
        self.companies = companies or list(GREENHOUSE_BOARDS.keys())

    async def fetch_jobs(self, companies: list[str] | None = None) -> list[Opportunity]:
        targets = companies or self.companies
        results = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for company in targets:
                board = GREENHOUSE_BOARDS.get(company, company)
                try:
                    resp = await client.get(
                        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                        params={"content": "true", "per_page": 100},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for job in data.get("jobs", []):
                        results.append(Opportunity(
                            title=job.get("title", ""),
                            company=company,
                            url=job.get("absolute_url", ""),
                            description=job.get("content", ""),
                            source="greenhouse_ats",
                            category="job",
                        ))
                except Exception:
                    continue
        return results

    async def check_live(self, url: str) -> bool:
        m = re.match(r"https://boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
        if not m:
            return False
        board, job_id = m.group(1), m.group(2)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
                )
                return resp.status_code == 200
            except Exception:
                return False
