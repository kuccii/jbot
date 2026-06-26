import re

import httpx

from job_bot.discovery.base import Opportunity
from job_bot.discovery.providers.base import ATSProvider

ASHBY_COMPANIES = [
    "linear", "notion", "rippling", "brex", "deel",
    "webflow", "lattice", "ashby",
]


class AshbyProvider(ATSProvider):
    name = "ashby"

    def __init__(self, companies: list[str] | None = None):
        self.companies = companies or list(ASHBY_COMPANIES)

    async def fetch_jobs(self, companies: list[str] | None = None) -> list[Opportunity]:
        targets = companies or self.companies
        results = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for company in targets:
                try:
                    resp = await client.post(
                        f"https://api.ashbyhq.com/posting-api/job-board/{company}",
                        json={"boardIdentifier": company},
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for job in data.get("jobBoard", {}).get("jobPostings", []):
                        results.append(Opportunity(
                            title=job.get("title", ""),
                            company=company,
                            url=job.get("jobUrl", ""),
                            description=job.get("descriptionPlain", ""),
                            source="ashby_ats",
                            location=job.get("location", ""),
                            category="job",
                        ))
                except Exception:
                    continue
        return results

    async def check_live(self, url: str) -> bool:
        m = re.match(r"https://jobs\.ashbyhq\.com/([^/]+)", url)
        if not m:
            return False
        company = m.group(1)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"https://api.ashbyhq.com/posting-api/job-board/{company}",
                    json={"boardIdentifier": company},
                )
                return resp.status_code == 200
            except Exception:
                return False
