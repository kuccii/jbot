import re

import httpx

from job_bot.discovery.base import Opportunity
from job_bot.discovery.providers.base import ATSProvider

LEVER_COMPANIES = [
    "stripe", "notion", "linear", "calendly", "deel",
    "brex", "canva", "webflow", "discord",
]


class LeverProvider(ATSProvider):
    name = "lever"

    def __init__(self, companies: list[str] | None = None):
        self.companies = companies or list(LEVER_COMPANIES)

    async def fetch_jobs(self, companies: list[str] | None = None) -> list[Opportunity]:
        targets = companies or self.companies
        results = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for company in targets:
                try:
                    resp = await client.get(
                        f"https://api.lever.co/v0/postings/{company}",
                        params={"limit": 100, "mode": "json"},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for job in data:
                        results.append(Opportunity(
                            title=job.get("text", ""),
                            company=company,
                            url=job.get("hostedUrl", ""),
                            description=job.get("description", ""),
                            source="lever_ats",
                            location=job.get("categories", {}).get("location", ""),
                            remote=job.get("categories", {}).get("commitment", ""),
                            category="job",
                        ))
                except Exception:
                    continue
        return results

    async def check_live(self, url: str) -> bool:
        m = re.match(r"https://jobs\.lever\.co/([^/]+)/([^/]+)", url)
        if not m:
            return False
        company, _ = m.group(1), m.group(2)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://api.lever.co/v0/postings/{company}",
                    params={"limit": 1},
                )
                return resp.status_code == 200
            except Exception:
                return False
