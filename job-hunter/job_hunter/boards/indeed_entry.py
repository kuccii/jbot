"""Indeed Entry-Level scraper — runs ONLY entry-level skills across countries.

The main IndeedBoard mixes tech + entry skills, so tech fills the limit
before entry skills get a chance. This board runs entry skills first,
ensuring we get customer support, VA, admin, IT support, data entry jobs.
"""

from __future__ import annotations

import asyncio
import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get_cf, get_proxied, get_proxy_manager
from job_hunter.models import Job, AUDIENCE_ENTRY, AUDIENCE_CREATIVE
from job_hunter.boards.indeed import COUNTRIES, _extract_jobs, _build_url

# Entry-level skills only — these are jobs accessible without a degree.
ENTRY_SKILLS: list[tuple[str, str]] = [
    # ── Customer Support / CX ─────────────────────────────────────────
    ("customer-support", AUDIENCE_ENTRY),
    ("chat-support", AUDIENCE_ENTRY),
    ("call-center-agent", AUDIENCE_ENTRY),
    ("help-desk", AUDIENCE_ENTRY),
    ("technical-support", AUDIENCE_ENTRY),
    ("it-support", AUDIENCE_ENTRY),
    ("it-help-desk", AUDIENCE_ENTRY),
    ("service-desk", AUDIENCE_ENTRY),
    # ── Virtual Assistant / Admin ──────────────────────────────────────
    ("virtual-assistant", AUDIENCE_ENTRY),
    ("administrative-assistant", AUDIENCE_ENTRY),
    ("executive-assistant", AUDIENCE_ENTRY),
    ("office-administrator", AUDIENCE_ENTRY),
    ("receptionist", AUDIENCE_ENTRY),
    ("office-clerk", AUDIENCE_ENTRY),
    # ── Data Entry / Typing ───────────────────────────────────────────
    ("data-entry-clerk", AUDIENCE_ENTRY),
    ("data-entry", AUDIENCE_ENTRY),
    ("data-operator", AUDIENCE_ENTRY),
    ("typing", AUDIENCE_ENTRY),
    # ── Transcription / Writing ───────────────────────────────────────
    ("transcriptionist", AUDIENCE_ENTRY),
    ("transcriber", AUDIENCE_ENTRY),
    ("proofreader", AUDIENCE_ENTRY),
    ("copywriter", AUDIENCE_CREATIVE),
    ("content-writer", AUDIENCE_CREATIVE),
    # ── Bookkeeping / Finance ─────────────────────────────────────────
    ("bookkeeper", AUDIENCE_ENTRY),
    ("accounts-payable", AUDIENCE_ENTRY),
    ("accounts-receivable", AUDIENCE_ENTRY),
    ("billing-clerk", AUDIENCE_ENTRY),
    ("payroll-clerk", AUDIENCE_ENTRY),
    # ── Scheduling / Coordination ─────────────────────────────────────
    ("scheduler", AUDIENCE_ENTRY),
    ("coordinator", AUDIENCE_ENTRY),
    ("dispatcher", AUDIENCE_ENTRY),
    # ── Social Media / Content ────────────────────────────────────────
    ("social-media-manager", AUDIENCE_CREATIVE),
    ("community-manager", AUDIENCE_ENTRY),
    ("content-moderator", AUDIENCE_ENTRY),
    ("moderator", AUDIENCE_ENTRY),
]

REQUEST_DELAY = 2.5  # seconds between requests


class IndeedEntryBoard(Board):
    """Scrapes Indeed for entry-level jobs only — customer support, VA,
    admin, IT support, data entry, transcription, bookkeeping, etc.

    Runs entry skills first across all countries to avoid rate limiting.
    """

    name = "indeed_entry"
    label = "Indeed Entry-Level (VA, CS, Admin, IT Support, Data Entry)"

    async def fetch(self, limit: int = 5000) -> list[Job]:
        all_jobs: list[Job] = []
        seen: set[str] = set()
        rate_limited = 0

        # Build tasks: entry skills first, international countries first
        tasks: list[tuple[str, str, str, str, str]] = []
        for domain, country in COUNTRIES:
            for skill, audience in ENTRY_SKILLS:
                url = _build_url(domain, skill, 0)
                tasks.append((url, domain, country, skill, audience))

        for url, domain, country, skill, audience in tasks:
            if len(all_jobs) >= limit:
                break
            if rate_limited >= 5:
                break

            # Try managed proxy first (ScraperAPI/ScrapingBee), then curl_cffi
            pm = get_proxy_manager()
            if pm.scraper_api_key or pm.scrapingbee_key:
                try:
                    async with self.client_proxied() as client:
                        resp = await get_proxied(client, url, timeout=20.0, retries=1)
                        result = resp.text
                except Exception:
                    result = await asyncio.to_thread(get_cf, url, 12.0, "safari")
            else:
                result = await asyncio.to_thread(get_cf, url, 12.0, "safari")

            if not result:
                rate_limited += 1
                await asyncio.sleep(5.0)
                continue

            if len(result) < 50000 and "429" in result[:500]:
                rate_limited += 1
                await asyncio.sleep(10.0)
                continue

            try:
                jobs = _extract_jobs(result, domain, country, skill)
            except Exception:
                continue

            if not jobs:
                continue

            for job in jobs:
                key = f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"
                if key in seen:
                    continue
                seen.add(key)

                tags = f"{skill} {job['country']}"
                if job["visa_sponsorship"]:
                    tags += " visa-sponsorship"

                all_jobs.append(Job(
                    title=job["title"],
                    company=job["company"],
                    url=job["url"],
                    board=self.name,
                    location="Remote",
                    remote="Remote",
                    tags=tags,
                    description=f"Indeed {job['country']}: {job['title']} at {job['company']}",
                    posted_at="",
                    eligible_countries=[],
                    audience=audience,
                ))

                if len(all_jobs) >= limit:
                    break

            await asyncio.sleep(REQUEST_DELAY)

        return all_jobs
