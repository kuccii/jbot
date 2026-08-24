"""Alignerr — AI training freelance jobs.

Scrapes https://www.alignerr.com/jobs which embeds a __NEXT_DATA__ JSON
payload containing all open roles with title, pay rate, description,
location, category, and apply URL.

These are REAL job listings:
  - "Software Engineer Task Author (AI Training)" — $70-120/hr
  - "Marketing Task Author (AI Training)" — $20-50/hr
  - "Audio Transcription & Alignment Specialist" — $15-35/hr

All jobs are Remote worldwide.
"""

from __future__ import annotations

import asyncio
import json
import re

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job, AUDIENCE_ENTRY

ALIGNERR_JOBS_URL = "https://www.alignerr.com/jobs"
BASE_URL = "https://www.alignerr.com"


class AlignerrBoard(Board):
    """Scrapes freelance AI training jobs from Alignerr."""

    name = "alignerr"
    label = "Alignerr — AI Training Jobs ($15-120/hr, Remote)"

    async def fetch(self, limit: int = 100) -> list[Job]:
        async with self.client() as client:
            resp = await get(client, ALIGNERR_JOBS_URL)
            text = resp.text

        # Extract JSON from __NEXT_DATA__ script tag
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.DOTALL
        )
        if not match:
            return []

        try:
            data = json.loads(match.group(1))
            raw_jobs = data["props"]["pageProps"]["initialJobs"]
        except (json.JSONDecodeError, KeyError):
            return []

        jobs: list[Job] = []
        seen = set()
        for item in raw_jobs:
            title = (item.get("title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)

            pay = item.get("pay", "")
            description = (item.get("description") or "").strip()
            location = item.get("location", "Remote")
            category = item.get("category", "")
            apply_path = item.get("applyUrl", "")
            apply_url = (
                f"{BASE_URL}{apply_path}" if apply_path.startswith("/") else apply_path
            )

            # Deduplicate by title — keep the one with the most info
            if len(description) > 50:
                full_desc = description
            else:
                full_desc = f"{title}\nPay: {pay}\nCategory: {category}\n{description}"

            jobs.append(Job(
                title=title,
                company="Alignerr",
                url=apply_url or ALIGNERR_JOBS_URL,
                board=self.name,
                location=location,
                remote="Remote",
                tags=f"ai-training {category}".strip(),
                description=full_desc,
                posted_at="",
                eligible_countries=[],
                audience=AUDIENCE_ENTRY,
            ))

        return jobs[:limit]
