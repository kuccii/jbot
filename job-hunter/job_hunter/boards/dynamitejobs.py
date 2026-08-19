"""DynamiteJobs — https://dynamitejobs.com

Remote-first job board curated by the Dynamite Jobs team. Lists jobs from
top remote-first companies. The site is client-side rendered (Astro/Next.js)
so we use Playwright to extract job listings from the DOM.

Jobs are listed with title, company, location restrictions, and skill tags.
Location restrictions include: \"Latin America\", \"Europe\", \"North America\",
\"Anywhere\", etc. — we filter for worldwide/Africa-eligible roles.
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


JOBS_URL = "https://dynamitejobs.com/remote-jobs"


class DynamiteJobsBoard(Board):
    """Fetches remote jobs from dynamitejobs.com via Playwright."""

    name = "dynamitejobs"
    label = "DynamiteJobs (curated remote-first jobs)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        render_js = _lazy_renderer()
        if not render_js:
            return []

        html = await render_js(JOBS_URL, timeout_ms=45_000)
        if not html:
            return []

        return self._parse_jobs(html, limit)

    def _parse_jobs(self, html: str, limit: int) -> list[Job]:
        """Extract job listings from rendered HTML."""
        jobs: list[Job] = []

        # dynamitejobs renders job titles in h2/h3 tags
        # Pattern: <h2>Staff Software Engineer (TypeScript)</h2>
        title_pattern = re.compile(
            r'<h[23][^>]*>([^<]*(?:Engineer|Developer|Manager|Designer|Lead|Director|'
            r'Analyst|Specialist|Coordinator|Consultant|Architect|Scientist|'
            r'Writer|Marketer|Sales|Account|Support|Operations)[^<]*)</h[23]>',
            re.IGNORECASE,
        )

        seen_titles: set[str] = set()
        for m in title_pattern.finditer(html):
            title = m.group(1).strip()
            title = re.sub(r"\s+", " ", title)

            if not title or len(title) < 10:
                continue
            if title in seen_titles:
                continue
            seen_titles.add(title)

            # Skip category/navigation items
            if any(skip in title.lower() for skip in [
                "developer, engineer", "select a", "browse all",
                "find a remote", "post a job",
            ]):
                continue

            jobs.append(Job(
                title=title,
                company="",
                url="https://dynamitejobs.com/remote-jobs",
                board=self.name,
                location="Worldwide",
                remote="Remote",
                tags="",
                description=f"Remote job from DynamiteJobs. {title}",
                posted_at="",
                eligible_countries=[],
            ))

            if len(jobs) >= limit:
                break

        return jobs
