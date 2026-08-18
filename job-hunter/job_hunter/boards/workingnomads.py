"""Working Nomads — https://www.workingnomads.com

Free public JSON API (no auth required):
  GET https://www.workingnomads.com/api/exposed_jobs/

Returns up to ~50 latest fully-remote jobs with a `location` field naming
the regions/countries applicants must be based in (e.g. "Worldwide",
"Europe, North America", ...). "Worldwide" or "Anywhere" = Rwanda-eligible;
restricted lists are rejected by the eligibility filter.

Note: volume is small (~50 jobs) and heavily dev-focused.
"""

from __future__ import annotations

import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

API_URL = "https://www.workingnomads.com/api/exposed_jobs/"

# location values that mean "open to anyone, anywhere".
WORLDWIDE_LOC = {"worldwide", "anywhere", "global", "remote", ""}


class WorkingNomadsBoard(Board):
    name = "workingnomads"
    label = "Working Nomads (fully remote jobs, free API)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        jobs: list[Job] = []
        async with self.client() as client:
            try:
                resp = await get(client, API_URL)
                data = resp.json()
            except Exception:
                return jobs

            for item in data if isinstance(data, list) else []:
                job = self._parse_job(item)
                if job:
                    jobs.append(job)

        # Worldwide jobs first — the raw feed mixes restricted locations in
        # front, so reorder so the eligible ones surface within the limit.
        jobs.sort(key=lambda j: j.location.strip().lower() not in WORLDWIDE_LOC)
        return jobs[:limit]

    def _parse_job(self, item: dict) -> Job | None:
        title = unescape(str(item.get("title", "")).strip())
        if not title:
            return None

        company = unescape(str(item.get("company_name", "")).strip())
        link = item.get("url", "")

        location = str(item.get("location", "")).strip()
        remote = "Remote" if location.lower() in ("worldwide", "anywhere", "global") else ""

        # Description is HTML
        desc_html = item.get("description", "") or ""
        desc = re.sub(r"<[^>]+>", " ", desc_html)
        desc = " ".join(desc.split())[:2000]

        return Job(
            title=title,
            company=company,
            url=link,
            board=self.name,
            location=location,
            remote=remote,
            tags=str(item.get("category_name", "")).strip(),
            description=desc,
            posted_at=str(item.get("pub_date", "")),
            eligible_countries=[],
        )
