"""Workday API scraper — entry-level, VA, data entry, customer support jobs.

Many large BPO/CX companies use Workday as their ATS. The Workday API
accepts POST requests with JSON body and returns structured job data.

The API endpoint pattern is:
  https://{company}.wd{N}.myworkdayjobs.com/wday/cxs/{company}/{site}/jobs

We scrape these companies for entry-level roles that are accessible to
people without college degrees — virtual assistants, data entry, customer
support, transcription, etc.
"""

from __future__ import annotations

import asyncio
import json

from job_hunter.boards.base import Board
from job_hunter.models import Job, AUDIENCE_ENTRY

# Workday company configurations.
# Format: (company_slug, wd_number, site_name, label, audience)
WORKDAY_COMPANIES: list[tuple[str, int, str, str, str]] = [
    # ── Entry-Level / CX / BPO Companies ──────────────────────────────
    ("modsquad", 5, "ModSquad_Contractor", "ModSquad (Contractor)", AUDIENCE_ENTRY),
    ("modsquad", 5, "ModSquad", "ModSquad (Full-Time)", AUDIENCE_ENTRY),
]

WORKDAY_API = "https://{company}.wd{wd}.myworkdayjobs.com/wday/cxs/{company}/{site}/jobs"


def _build_url(company: str, wd: int, site: str) -> str:
    return WORKDAY_API.format(company=company, wd=wd, site=site)


def _post_workday(url: str) -> str | None:
    """POST to Workday API and return response text."""
    try:
        from curl_cffi import requests as cffi_requests
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        r = cffi_requests.post(url, impersonate="safari", timeout=15, headers=headers, json={})
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def _extract_jobs(data: dict, company: str, site: str, audience: str) -> list[dict]:
    """Extract job data from Workday API response."""
    jobs = []
    for posting in data.get("jobPostings", []):
        title = (posting.get("title") or "").strip()
        if not title:
            continue

        # Build the detail URL
        ext_path = posting.get("externalPath", "")
        detail_url = f"https://{company}.wd5.myworkdayjobs.com/en-US/{site}{ext_path}" if ext_path else ""

        location = posting.get("locationsText", "")
        posted = posting.get("postedOn", "")
        time_type = posting.get("timeType", "")
        bullets = posting.get("bulletFields", [])
        job_id = bullets[0] if bullets else ""

        is_remote = any(
            kw in title.lower() or kw in location.lower()
            for kw in ["remote", "work from home", "wfh", "virtual", "anywhere"]
        )

        # For eligibility: if title says Remote, use "Remote" as location
        # The original location text (e.g. "2 Locations") is too vague
        eligible_location = "Remote" if is_remote else location

        jobs.append({
            "title": title,
            "company": company.title(),
            "url": detail_url,
            "location": eligible_location,
            "remote": "Remote" if is_remote else "",
            "posted": posted,
            "time_type": time_type,
            "job_id": job_id,
            "audience": audience,
        })

    return jobs


class WorkdayBoard(Board):
    """Scrapes Workday APIs for entry-level/VA/data entry/CX jobs.

    Companies use Workday as their ATS and expose a public JSON API.
    We scrape all configured companies and filter for entry-level roles.
    """

    name = "workday"
    label = "Workday (Entry-Level / VA / CX)"

    async def fetch(self, limit: int = 500) -> list[Job]:
        all_jobs: list[Job] = []
        seen: set[str] = set()

        for company, wd, site, label, audience in WORKDAY_COMPANIES:
            url = _build_url(company, wd, site)
            result = await asyncio.to_thread(_post_workday, url)

            if not result:
                continue

            try:
                data = json.loads(result)
            except (json.JSONDecodeError, ValueError):
                continue

            total = data.get("total", 0)
            if total == 0:
                continue

            jobs = _extract_jobs(data, company, site, audience)

            # If more jobs available, paginate
            if total > len(jobs):
                for offset in range(20, min(total, 200), 20):
                    page_url = f"{url}?offset={offset}"
                    page_result = await asyncio.to_thread(_post_workday, page_url)
                    if page_result:
                        try:
                            page_data = json.loads(page_result)
                            page_jobs = _extract_jobs(page_data, company, site, audience)
                            jobs.extend(page_jobs)
                        except (json.JSONDecodeError, ValueError):
                            break
                    await asyncio.sleep(1.0)

            for job in jobs:
                key = f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"
                if key in seen:
                    continue
                seen.add(key)

                all_jobs.append(Job(
                    title=job["title"],
                    company=job["company"],
                    url=job["url"],
                    board=self.name,
                    location=job["location"],
                    remote=job["remote"],
                    tags=f"{label} {job['time_type']}",
                    description=f"Workday: {job['title']} at {job['company']} ({job['location']})",
                    posted_at=job["posted"],
                    eligible_countries=[],
                    audience=job["audience"],
                ))

                if len(all_jobs) >= limit:
                    break

            if len(all_jobs) >= limit:
                break

        return all_jobs
