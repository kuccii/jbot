"""Indeed.com scraper — uses Safari impersonation to bypass anti-bot.

Indeed blocks Chrome/Firefox impersonation but allows Safari. We use
curl_cffi with Safari impersonation to scrape job listings directly.

Search queries are configured for Rwanda-friendly remote jobs with
relevant keywords (Python, AI/ML, Full Stack, etc.).
"""

from __future__ import annotations

import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get_cf
from job_hunter.models import Job

# Search queries for Rwanda-friendly remote jobs
SEARCH_QUERIES = [
    "remote python developer",
    "remote software engineer",
    "remote data scientist",
    "remote AI machine learning",
    "remote full stack developer",
    "remote devops engineer",
    "remote product manager",
    "remote UX designer",
    "remote data analyst",
    "remote content writer",
    "remote customer support",
    "remote virtual assistant",
    "freelance developer worldwide",
    "remote jobs africa",
]


def _build_indeed_url(query: str) -> str:
    """Build an Indeed search URL."""
    return f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l="


def _extract_jobs(html: str, query: str) -> list[dict]:
    """Extract job data from Indeed HTML."""
    jobs = []

    # Extract titles (id="jobTitle-xxx")
    titles = re.findall(r'<span[^>]*id="jobTitle-[^"]*"[^>]*>([^<]+)</span>', html)

    # Extract companies (data-testid="company-name")
    companies = re.findall(r'data-testid="company-name"[^>]*>([^<]+)<', html)

    # Extract locations (data-testid="text-location")
    locations = re.findall(r'data-testid="text-location"[^>]*>([^<]+)<', html)

    # Extract job URLs
    urls = re.findall(r'href="(/rc/clk[^"]+)"', html)

    # Match jobs by position
    for i in range(min(len(titles), len(companies), len(urls))):
        title = unescape(titles[i]).strip()
        company = unescape(companies[i]).strip()
        location = unescape(locations[i]).strip() if i < len(locations) else ""
        url = f"https://www.indeed.com{urls[i]}"

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "query": query,
        })

    return jobs


class IndeedBoard(Board):
    """Scrapes Indeed.com for remote jobs using Safari impersonation."""

    name = "indeed"
    label = "Indeed.com (remote job search)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        all_jobs: list[Job] = []
        seen_titles: set[str] = set()

        for query in SEARCH_QUERIES:
            if len(all_jobs) >= limit:
                break

            try:
                url = _build_indeed_url(query)
                html = get_cf(url, timeout=15, impersonate="safari")
                if not html:
                    continue

                jobs = _extract_jobs(html, query)

                for job in jobs:
                    # Deduplicate by title + company
                    key = f"{job['title'].lower()}|{job['company'].lower()}"
                    if key in seen_titles:
                        continue
                    seen_titles.add(key)

                    # Determine remote status
                    loc = job["location"].lower()
                    is_remote = "remote" in loc or "worldwide" in loc or "anywhere" in loc
                    remote = "Remote" if is_remote else ""

                    all_jobs.append(Job(
                        title=job["title"],
                        company=job["company"],
                        url=job["url"],
                        board=self.name,
                        location=job["location"],
                        remote=remote,
                        tags=job["query"],
                        description=f"Indeed job listing: {job['title']} at {job['company']}",
                        posted_at="",
                        eligible_countries=[],
                    ))

                    if len(all_jobs) >= limit:
                        break

            except Exception:
                continue  # One failing query must not kill the board

        return all_jobs
