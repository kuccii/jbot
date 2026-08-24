import html
import re

import httpx
from bs4 import BeautifulSoup

from job_bot.discovery.base import Opportunity
from job_bot.discovery.providers.base import ATSProvider


def _strip_html(raw: str) -> str:
    """Convert HTML to plain text, handling common entities and tags."""
    if not raw:
        return ""
    decoded = html.unescape(raw)
    soup = BeautifulSoup(decoded, "html.parser")
    return soup.get_text(separator=" ", strip=True)

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
                        location = ""
                        loc_obj = job.get("location") or {}
                        if isinstance(loc_obj, dict):
                            location = loc_obj.get("name", "") or ""
                        elif isinstance(loc_obj, str):
                            location = loc_obj
                        if not location:
                            offices = job.get("offices") or []
                            parts = []
                            for o in offices:
                                loc = o.get("location") or ""
                                if loc:
                                    parts.append(loc)
                            location = "; ".join(parts)
                        remote_str = ""
                        if job.get("remote"):
                            remote_str = "remote"
                        results.append(Opportunity(
                            title=job.get("title", ""),
                            company=company,
                            url=job.get("absolute_url", ""),
                            description=_strip_html(job.get("content", "")),
                            source="greenhouse_ats",
                            category="job",
                            location=location,
                            remote=remote_str,
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
