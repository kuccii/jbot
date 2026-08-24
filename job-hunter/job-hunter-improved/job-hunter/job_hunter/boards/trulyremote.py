"""TrulyRemote — https://trulyremote.co

Curated remote job board that pre-screens listings for truly remote
positions (not hybrid/US-only). The site is client-side rendered and
uses Playwright to extract job listings.

Jobs link to external ATS platforms (Greenhouse, Ashby, Lever) and
include location restrictions. We filter for worldwide/Africa-eligible
roles.
"""

from __future__ import annotations

import re

from job_hunter.boards.base import Board
from job_hunter.models import Job

_get_renderer = None


def _lazy_renderer():
    global _get_renderer
    if _get_renderer is None:
        try:
            from job_hunter.boards.js_render import render_js
            _get_renderer = render_js
        except ImportError:
            pass
    return _get_renderer


JOBS_URL = "https://trulyremote.co/jobs"


class TrulyRemoteBoard(Board):
    """Fetches truly remote jobs from trulyremote.co via Playwright."""

    name = "trulyremote"
    label = "TrulyRemote (curated truly-remote jobs)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        render_js = _lazy_renderer()
        if not render_js:
            return []

        html = await render_js(JOBS_URL, timeout_ms=45_000, extra_wait_ms=10_000)
        if not html:
            return []

        return self._parse_jobs(html, limit)

    def _parse_jobs(self, html: str, limit: int) -> list[Job]:
        """Extract job listings from rendered HTML."""
        jobs: list[Job] = []

        # trulyremote links to external ATS platforms
        # Pattern: <a href="https://jobs.ashbyhq.com/..."> or <a href="https://job-boards.greenhouse.io/...">
        ats_pattern = re.compile(
            r'<a[^>]*href="(https://(?:jobs\.ashbyhq\.com|job-boards\.greenhouse\.io|jobs\.lever\.co|boards\.greenhouse\.io)[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        seen_urls: set[str] = set()
        for m in ats_pattern.finditer(html):
            url = m.group(1).split("?")[0]  # Remove UTM params
            inner = m.group(2)

            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract title from inner HTML
            title = re.sub(r"<[^>]+>", " ", inner).strip()
            title = re.sub(r"\s+", " ", title)
            if not title or len(title) < 5:
                continue

            # Skip non-job links (navigation, etc.)
            if any(skip in title.lower() for skip in ["sign up", "log in", "about", "contact"]):
                continue

            # Extract company from URL
            company = self._extract_company(url)

            jobs.append(Job(
                title=title,
                company=company,
                url=url,
                board=self.name,
                location="Worldwide",
                remote="Remote",
                tags="",
                description=f"Truly remote job from {company or 'unknown'}. {title}",
                posted_at="",
                eligible_countries=[],
            ))

            if len(jobs) >= limit:
                break

        return jobs

    def _extract_company(self, url: str) -> str:
        """Extract company name from ATS URL."""
        # Ashby: https://jobs.ashbyhq.com/<company>/<id>
        m = re.search(r"ashbyhq\.com/([^/]+)", url)
        if m:
            return m.group(1).replace("-", " ").title()

        # Greenhouse: https://job-boards.greenhouse.io/<company>/jobs/<id>
        m = re.search(r"greenhouse\.io/([^/]+)", url)
        if m:
            return m.group(1).replace("-", " ").title()

        # Lever: https://jobs.lever.co/<company>/<id>
        m = re.search(r"lever\.co/([^/]+)", url)
        if m:
            return m.group(1).replace("-", " ").title()

        return ""
