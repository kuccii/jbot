"""FoundTheJob.com — https://foundthejob.com

WordPress-based job board with a public REST API. Jobs are stored as
standard WP posts accessible via ``/wp-json/wp/v2/posts``. Each post has
a title, date, link, and HTML content with job details.

The site focuses on Indian job listings (walk-in drives, campus hiring),
but includes some remote/work-from-home roles.  We filter for remote-
eligible positions and extract location signals from the content.
"""

from __future__ import annotations

import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.boards.utils import strip_html
from job_hunter.fetch import get
from job_hunter.models import Job

API_URL = "https://foundthejob.com/wp-json/wp/v2/posts"
PER_PAGE = 20  # keep request count bounded


class FoundTheJobBoard(Board):
    """Fetches job listings from FoundTheJob.com via WP REST API."""

    name = "foundthejob"
    label = "FoundTheJob.com (WordPress job board)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        try:
            resp = await get(
                self.client(),
                f"{API_URL}?per_page={PER_PAGE}&_fields=id,title,date,link,content",
            )
            data = resp.json()
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        jobs: list[Job] = []
        for item in data:
            job = self._parse_post(item)
            if job:
                jobs.append(job)
            if len(jobs) >= limit:
                break
        return jobs

    def _parse_post(self, item: dict) -> Job | None:
        title_raw = (item.get("title") or {}).get("rendered", "")
        title = unescape(strip_html(title_raw)).strip()
        if not title:
            return None

        url = item.get("link") or ""
        content_html = (item.get("content") or {}).get("rendered", "")
        description = strip_html(content_html)

        # Extract location signals from content
        location = self._extract_location(description)
        remote = self._is_remote(title, description)

        return Job(
            title=title,
            company="",  # WP posts don't have structured company field
            url=url,
            board=self.name,
            location=location,
            remote=remote,
            tags="",
            description=description[:2000],
            posted_at=str(item.get("date", "")),
            eligible_countries=[],
        )

    def _extract_location(self, text: str) -> str:
        """Try to pull a city/country from the description text."""
        text_lower = text.lower()

        # Look for common patterns: "in <City>", "at <City>", location fields
        patterns = [
            r"(?:in|at|location[:\s]+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"(?:city|location|place)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1)

        # Check for remote/WFH signals
        if any(w in text_lower for w in ["work from home", "wfh", "remote", "online"]):
            return "Remote"

        return ""

    def _is_remote(self, title: str, description: str) -> str:
        """Return 'Remote' if the job appears to be remote."""
        combined = f"{title} {description}".lower()
        remote_signals = [
            "work from home", "wfh", "remote", "online",
            "work from anywhere", "telecommute",
        ]
        if any(s in combined for s in remote_signals):
            return "Remote"
        return ""
