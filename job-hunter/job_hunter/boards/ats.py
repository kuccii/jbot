"""Direct company postings via ATS job-board APIs.

Companies post jobs on applicant tracking systems. Three of the major
ones expose public JSON APIs (no auth, no scraping):

  Greenhouse        GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
  Ashby             GET https://api.ashbyhq.com/posting-api/job-board/{slug}
  SmartRecruiters   GET https://api.smartrecruiters.com/v1/companies/{slug}/postings

Each returns structured location data:
  - Greenhouse:       location.name        ("Remote, Italy")
  - Ashby:            location + isRemote  ("Americas / Remote / Full-time", True)
  - SmartRecruiters:  location.fullLocation + location.remote bool

Lever's public API was retired (404s on every company) so it is not
supported. The company list lives in config (`ats_companies`), each entry
being {name, ats, slug}. Only ATS slugs that resolve live are seeded.
"""

from __future__ import annotations

import asyncio
import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"


def _strip_html(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", text or "").split())[:2000]


class ATSBoard(Board):
    """Fetches postings from the ATS boards of configured companies."""

    name = "ats"
    label = "Direct company postings (Greenhouse / Ashby / SmartRecruiters)"

    def __init__(self, companies: list[dict] | None = None, transport=None):
        super().__init__(transport)
        # companies: [{name, ats, slug}, ...] — normalize to dicts.
        self.companies = [dict(c) for c in (companies or [])]

    # Max postings fetched per company per run. Keeps the request count
    # bounded while still sampling each company's board.
    PER_COMPANY_LIMIT = 10

    async def fetch(self, limit: int = 30) -> list[Job]:
        if not self.companies:
            return []
        per_company = min(self.PER_COMPANY_LIMIT, max(1, limit))
        async with self.client() as client:
            # Fetch every company's board concurrently — sequential calls
            # across 24 companies take ~1 minute.
            batches = await asyncio.gather(
                *(self._fetch_company(client, company, per_company)
                  for company in self.companies)
            )

        # Round-robin merge so the limit is spread across all companies
        # instead of being consumed by the first ones on the list.
        jobs: list[Job] = []
        queue = [b for b in batches if b]
        while queue and len(jobs) < limit:
            next_round: list[list[Job]] = []
            for batch in queue:
                if batch:
                    jobs.append(batch.pop(0))
                    if len(jobs) >= limit:
                        break
                if batch:
                    next_round.append(batch)
            queue = next_round
        return jobs[:limit]

    async def _fetch_company(self, client, company: dict, per_company: int) -> list[Job]:
        ats = str(company.get("ats", "")).lower()
        slug = str(company.get("slug", ""))
        if not slug:
            return []
        try:
            if ats == "greenhouse":
                batch = await self._fetch_greenhouse(client, company)
            elif ats == "ashby":
                batch = await self._fetch_ashby(client, company)
            elif ats == "smartrecruiters":
                batch = await self._fetch_smartrecruiters(client, company)
            else:
                batch = []
        except Exception:
            batch = []  # one failing company must not kill the board
        return batch[:per_company]

    async def _fetch_greenhouse(self, client, company: dict) -> list[Job]:
        resp = await get(client, GREENHOUSE_API.format(slug=company["slug"]))
        data = resp.json()
        out: list[Job] = []
        for item in data.get("jobs", []):
            title = unescape(str(item.get("title", "")).strip())
            if not title:
                continue
            loc = (item.get("location") or {})
            location = str(loc.get("name", "")).strip() if isinstance(loc, dict) else str(loc)
            remote = "Remote" if "remote" in location.lower() else ""
            desc = _strip_html(item.get("content", ""))
            out.append(Job(
                title=title,
                company=company.get("name", item.get("company_name", "")),
                url=item.get("absolute_url", ""),
                board=self.name,
                location=location,
                remote=remote,
                tags="",
                description=desc,
                posted_at=str(item.get("first_published", "")),
                eligible_countries=[],
            ))
        return out

    async def _fetch_ashby(self, client, company: dict) -> list[Job]:
        resp = await get(client, ASHBY_API.format(slug=company["slug"]))
        data = resp.json()
        out: list[Job] = []
        for item in data.get("jobs", []):
            title = unescape(str(item.get("title", "")).strip())
            if not title or not item.get("isListed", True):
                continue
            location = str(item.get("location", "")).strip()
            remote = "Remote" if item.get("isRemote") or "remote" in location.lower() else ""
            desc = _strip_html(item.get("descriptionPlain", ""))
            out.append(Job(
                title=title,
                company=company.get("name", ""),
                url=item.get("jobUrl", "") or item.get("applyUrl", ""),
                board=self.name,
                location=location,
                remote=remote,
                tags=str(item.get("department", "")),
                description=desc,
                posted_at=str(item.get("publishedAt", "")),
                eligible_countries=[],
            ))
        return out

    async def _fetch_smartrecruiters(self, client, company: dict) -> list[Job]:
        resp = await get(client, SMARTRECRUITERS_API.format(slug=company["slug"]))
        data = resp.json()
        out: list[Job] = []
        for item in data.get("content", []):
            title = unescape(str(item.get("name", "")).strip())
            if not title:
                continue
            loc = item.get("location") or {}
            full_loc = str(loc.get("fullLocation", "")).strip()
            country = str(loc.get("country", "")).strip()
            remote_flag = bool(loc.get("remote"))
            location = full_loc or (f"{country} (Remote)" if remote_flag else country)
            remote = "Remote" if remote_flag else ""
            out.append(Job(
                title=title,
                company=company.get("name", ""),
                url=item.get("url", ""),
                board=self.name,
                location=location,
                remote=remote,
                tags="",
                description="",
                posted_at=str(item.get("releasedDate", "")),
                eligible_countries=[],
            ))
        return out
