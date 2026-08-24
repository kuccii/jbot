"""Himalayas — https://himalayas.app

Free public JSON API (no auth required):
  GET https://himalayas.app/jobs/api?limit=20&offset=0
  GET https://himalayas.app/jobs/api/search?worldwide=true

The API returns structured job data including `locationRestrictions` — an
array of country codes where applicants must be based. An empty array means
the job is worldwide-eligible (open to anyone, anywhere).

This is one of the best sources for worldwide-eligible remote roles because:
  1. The data is structured and reliable (no HTML parsing needed)
  2. `locationRestrictions` gives deterministic Rwanda eligibility
  3. 100K+ jobs in the feed, refreshed daily
"""

from __future__ import annotations

from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

API_BASE = "https://himalayas.app/jobs/api"
WORLDWIDE_SEARCH = "https://himalayas.app/jobs/api/search?worldwide=true"


class HimalayasBoard(Board):
    name = "himalayas"
    label = "Himalayas (worldwide remote, structured API)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        jobs: list[Job] = []

        # Strategy: fetch worldwide jobs first (guaranteed Rwanda-eligible),
        # then fill with keyword-matched jobs from the general feed.
        async with self.client() as client:
            # 1. Worldwide-only jobs
            try:
                resp = await get(client, WORLDWIDE_SEARCH)
                data = resp.json()
                for item in data.get("jobs", []):
                    job = self._parse_job(item)
                    if job:
                        jobs.append(job)
                    if len(jobs) >= limit:
                        break
            except Exception:
                pass  # one failing feed must not kill the board

            # 2. General feed (may include country-restricted jobs — eligibility
            #    filter will reject non-worldwide ones).
            if len(jobs) < limit:
                try:
                    resp = await get(client, f"{API_BASE}?limit=20&offset=0")
                    data = resp.json()
                    for item in data.get("jobs", []):
                        job = self._parse_job(item)
                        if job and not any(j.url == job.url for j in jobs):
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

        company = unescape(str(item.get("companyName", "")).strip())
        link = item.get("applicationLink", "") or item.get("guid", "")

        # Location restrictions: empty array = worldwide
        restrictions = item.get("locationRestrictions") or []
        country_codes = [c for c in restrictions if c]

        # Build location text from restrictions
        if not country_codes:
            location = "Worldwide"
        else:
            location = ", ".join(country_codes)

        # Salary info
        min_sal = item.get("minSalary")
        max_sal = item.get("maxSalary")
        currency = item.get("currency", "")
        salary_text = ""
        if min_sal and max_sal:
            salary_text = f"{currency} {min_sal:,.0f}–{max_sal:,.0f}"

        # Categories
        categories = item.get("categories") or []
        tags = ", ".join(categories[:5])

        # Description excerpt
        description = unescape(str(item.get("excerpt", "")).strip())[:2000]

        return Job(
            title=title,
            company=company,
            url=link,
            board=self.name,
            location=location,
            remote="Remote" if not country_codes else "",
            tags=tags,
            description=description,
            posted_at=str(item.get("pubDate", "")),
            eligible_countries=[],  # empty = worldwide (eligible via heuristic)
        )
