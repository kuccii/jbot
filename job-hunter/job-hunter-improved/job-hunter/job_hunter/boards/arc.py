"""Arc.dev — https://arc.dev/remote-jobs

Remote developer job board. The listing page is a Next.js app that embeds
job data in a ``<script id="__NEXT_DATA__">`` tag as JSON. Each job has:

  - title, jobType, jobRole
  - timeZone ("no-preference" | "Central Time (US & Canada)" | ...)
  - requiredCountries ([] = worldwide, ["US"] = US only, ...)
  - overlapHours (None or int)
  - urlString (slug for the detail page)
  - postedAt

We parse the JSON directly — no browser rendering needed. The list page
returns 30 jobs; pagination is client-side so we only fetch page 1 per run.
"""

from __future__ import annotations

import json
import re

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

LIST_URL = "https://arc.dev/remote-jobs"
DETAIL_BASE = "https://arc.dev/remote-jobs/"

# Timezone strings that indicate a US/EU-only restriction.
_RESTRICTED_TZS = {
    "central time (us & canada)",
    "eastern time (us & canada)",
    "pacific time (us & canada)",
    "mountain time (us & canada)",
    "us eastern",
    "us pacific",
    "us central",
    "us mountain",
    "gmt-5",
    "gmt-6",
    "gmt-7",
    "gmt-8",
    "cet",
    "cest",
    "utc+1",
    "utc+2",
}


class ArcBoard(Board):
    """Fetches remote developer jobs from arc.dev."""

    name = "arc"
    label = "Arc.dev (remote developer jobs)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        try:
            resp = await get(self.client(), LIST_URL)
            html = resp.text
        except Exception:
            return []

        # Extract __NEXT_DATA__ JSON
        m = re.search(r'__NEXT_DATA__.*?>(.*?)</script>', html)
        if not m:
            return []

        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            return []

        raw_jobs = (
            data.get("props", {})
            .get("pageProps", {})
            .get("arcJobs", [])
        )
        if not raw_jobs:
            return []

        jobs: list[Job] = []
        for item in raw_jobs:
            job = self._parse_job(item)
            if job:
                jobs.append(job)
            if len(jobs) >= limit:
                break
        return jobs

    def _parse_job(self, item: dict) -> Job | None:
        title = (item.get("title") or "").strip()
        if not title:
            return None

        slug = item.get("urlString") or ""
        url = DETAIL_BASE + slug if slug else ""

        # Company info — arc.dev nests it differently
        company_data = item.get("company") or {}
        company = company_data.get("name", "") or ""

        # Timezone / country restrictions
        tz = (item.get("timeZone") or "").strip()
        required_countries = item.get("requiredCountries") or []
        overlap = item.get("overlapHours")

        # Determine remote status and location
        location = ""
        remote = ""

        if not required_countries and tz.lower() == "no-preference":
            # Truly worldwide — no restrictions
            location = "Worldwide"
            remote = "Remote"
        elif required_countries:
            # Specific countries required
            location = ", ".join(required_countries)
            remote = ""
        elif tz.lower() in _RESTRICTED_TZS:
            # US/EU timezone restriction
            location = tz
            remote = ""
        else:
            # Other timezone — might still be open
            location = tz
            remote = "Remote" if "no-preference" in tz.lower() else ""

        # Job type and role for context
        job_type = item.get("jobType") or ""
        role = item.get("jobRole") or ""

        # Posted date
        posted = item.get("postedAt") or ""

        return Job(
            title=title,
            company=company,
            url=url,
            board=self.name,
            location=location,
            remote=remote,
            tags=f"{role},{job_type}" if role else job_type,
            description="",
            posted_at=str(posted),
            eligible_countries=required_countries,
        )
