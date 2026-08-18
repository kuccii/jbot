"""Jobicy — https://jobicy.com

Free public JSON API (no auth required):
  GET https://jobicy.com/api/v2/remote-jobs?count=100

The `jobGeo` field is the geographic employment restriction, or "Anywhere"
when no region is specified — that is the Rwanda-eligibility signal.
Filterable by `geo`, `industry`, and `tag` if needed.

Note: the feed skews heavily to US/Canada/EU-restricted roles, so the
eligible yield is low (~5%), but the API is reliable and every "Anywhere"
listing is cleanly worldwide.
"""

from __future__ import annotations

import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

API_URL = "https://jobicy.com/api/v2/remote-jobs?count=100"

# geo values that mean "open to anyone, anywhere".
WORLDWIDE_GEO = {"anywhere", "worldwide", "global"}


class JobicyBoard(Board):
    name = "jobicy"
    label = "Jobicy (remote jobs API, geo-restriction field)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        jobs: list[Job] = []
        async with self.client() as client:
            try:
                resp = await get(client, API_URL)
                data = resp.json()
            except Exception:
                return jobs

            for item in data.get("jobs", []):
                job = self._parse_job(item)
                if job:
                    jobs.append(job)

        # Worldwide jobs first — the raw feed is dominated by US/Canada/EU
        # roles, so without reordering the eligible ones never surface.
        jobs.sort(key=lambda j: j.location.lower() not in WORLDWIDE_GEO)
        return jobs[:limit]

    def _parse_job(self, item: dict) -> Job | None:
        title = unescape(str(item.get("jobTitle", "")).strip())
        if not title:
            return None

        company = unescape(str(item.get("companyName", "")).strip())
        link = item.get("url", "")

        geo = str(item.get("jobGeo", "")).strip()
        location = geo if geo else "Anywhere"
        remote = "Remote" if location.lower() in ("anywhere", "worldwide", "global") else ""

        # Description is HTML
        desc_html = item.get("jobDescription", "") or ""
        desc = re.sub(r"<[^>]+>", " ", desc_html)
        desc = " ".join(desc.split())[:2000]

        industries = item.get("jobIndustry") or []
        tags = ", ".join(industries[:5])

        return Job(
            title=title,
            company=company,
            url=link,
            board=self.name,
            location=location,
            remote=remote,
            tags=tags,
            description=desc,
            posted_at=str(item.get("pubDate", "")),
            eligible_countries=[],
        )
