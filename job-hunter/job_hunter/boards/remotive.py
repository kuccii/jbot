"""Remotive — https://remotive.com

Free public JSON API (no auth required):
  GET https://remotive.com/api/remote-jobs
  GET https://remotive.com/api/remote-jobs?category=software-dev
  GET https://remotive.com/api/remote-jobs?limit=5

The `candidate_required_location` field indicates geographic restrictions.
"Worldwide" = open to anyone. Otherwise it lists specific countries.

Note: API data is delayed by 24 hours. Rate limit: max 2x/min.
"""

from __future__ import annotations

from html import unescape

from job_hunter.boards.base import Board
from job_hunter.boards.utils import strip_html, remote_status
from job_hunter.fetch import get
from job_hunter.models import Job

API_URL = "https://remotive.com/api/remote-jobs"

# African countries that include Rwanda in their hiring radius.
AFRICA_COUNTRIES = {
    "rwanda", "kenya", "uganda", "tanzania", "burundi", "ethiopia",
    "south sudan", "congo", "dr congo", "democratic republic of congo",
    "mozambique", "zambia", "zimbabwe", "malawi", "botswana", "namibia",
    "south africa", "nigeria", "ghana", "senegal", "cameroon", "ivory coast",
    "côte d'ivoire", "africa", "east africa", "sub-saharan africa",
    "emea", "middle east and africa",
}


class RemotiveBoard(Board):
    name = "remotive"
    label = "Remotive (worldwide remote, free API)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        jobs: list[Job] = []

        async with self.client() as client:
            # Fetch worldwide jobs first (guaranteed eligible)
            try:
                resp = await get(client, API_URL)
                data = resp.json()
                for item in data.get("jobs", []):
                    job = self._parse_job(item)
                    if job:
                        jobs.append(job)
                    if len(jobs) >= limit:
                        break
            except Exception:
                pass

        return jobs[:limit]

    def _parse_job(self, item: dict) -> Job | None:
        title = unescape(str(item.get("title", "")).strip())
        if not title:
            return None

        company = unescape(str(item.get("company_name", "")).strip())
        link = item.get("url", "")

        # Geographic restriction
        required_loc = str(item.get("candidate_required_location", "")).strip()
        location = required_loc if required_loc else ""

        # Determine remote status
        remote = remote_status(location)

        # Salary
        salary = str(item.get("salary", "")).strip()

        # Category
        category = str(item.get("category", "")).strip()

        desc = strip_html(item.get("description", ""))

        return Job(
            title=title,
            company=company,
            url=link,
            board=self.name,
            location=location,
            remote=remote,
            tags=category,
            description=desc,
            posted_at=str(item.get("publication_date", "")),
            eligible_countries=[],  # empty = worldwide (eligible via heuristic)
        )
