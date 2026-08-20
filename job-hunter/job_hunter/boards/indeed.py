"""Indeed.com multi-country scraper — scrapes 12+ country domains.

Indeed blocks Chrome/Firefox impersonation but allows Safari. We use
curl_cffi with Safari impersonation to scrape job listings from multiple
country-specific Indeed domains. Each domain uses the /remote-*-jobs
path which returns structured job data.

Countries are chosen to maximize Rwanda/Kenya-relevant remote job yields.
"""

from __future__ import annotations

import asyncio
import re
from html import unescape
from urllib.parse import quote_plus

from job_hunter.boards.base import Board
from job_hunter.fetch import get_cf
from job_hunter.models import Job

# Country domains and their search configurations.
# The /remote-*-jobs path works across all Indeed country domains.
COUNTRIES = [
    # (domain, label, skill_queries)
    ("www.indeed.com", "US", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning-engineer", "full-stack-developer",
        "devops-engineer", "product-manager", "ux-designer",
    ]),
    ("www.indeed.co.uk", "UK", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.de", "Germany", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.nl", "Netherlands", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.ie", "Ireland", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.fr", "France", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.ca", "Canada", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.com.au", "Australia", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.sg", "Singapore", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.co.za", "S.Africa", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.co.in", "India", [
        "python-developer", "software-engineer", "data-scientist",
        "machine-learning", "full-stack-developer", "devops-engineer",
    ]),
    ("www.indeed.com", "US-wide", [
        "work-from-home", "remote-jobs", "freelance-developer",
        "worldwide-remote", "anywhere-remote",
    ]),
]

# How many pages to scrape per country-query combo (10 jobs per page)
MAX_PAGES = 2


def _build_url(domain: str, skill: str, start: int = 0) -> str:
    """Build an Indeed country URL using the /remote-*-jobs path."""
    path = f"/remote-{skill}-jobs"
    if start > 0:
        path += f"?start={start}"
    return f"https://{domain}{path}"


def _extract_jobs(html: str, domain: str, country: str, skill: str) -> list[dict]:
    """Extract job data from Indeed HTML.

    Indeed renders job cards in a mosaic grid. We extract from:
    - <a> tags with class containing 'jcs-JobTitle' (title + URL)
    - data-testid="company-name" (company)
    - data-testid="text-location" (location)
    """
    jobs = []

    # Extract titles from jcs-JobTitle links
    title_blocks = re.findall(
        r'<a[^>]*class="[^"]*jcs-JobTitle[^"]*"[^>]*href="([^"]*)"[^>]*>'
        r'<span[^>]*>([^<]+)</span></a>',
        html, re.DOTALL,
    )

    # Fallback: extract from id="jobTitle-xxx" spans
    if not title_blocks:
        title_spans = re.findall(
            r'<span[^>]*id="jobTitle-[^"]*"[^>]*>([^<]+)</span>',
            html,
        )
        # Find corresponding URLs
        urls = re.findall(r'href="(/rc/clk[^"]*)"', html)
        for i, title in enumerate(title_spans):
            url = urls[i] if i < len(urls) else ""
            title_blocks.append((url, unescape(title).strip()))

    # Extract companies
    companies = re.findall(
        r'data-testid="company-name"[^>]*>([^<]+)<', html
    )
    if not companies:
        # Fallback: company name in span inside companyInfo
        companies = re.findall(
            r'<span[^>]*data-testid="company-name"[^>]*>([^<]+)</span>', html
        )

    # Extract locations
    locations = re.findall(
        r'data-testid="text-location"[^>]*>([^<]+)<', html
    )
    if not locations:
        locations = re.findall(
            r'<div[^>]*class="[^"]*companyLocation[^"]*"[^>]*>([^<]+)</div>', html
        )

    for i, (url_path, title) in enumerate(title_blocks):
        if not title or len(title) < 3:
            continue

        company = unescape(companies[i]).strip() if i < len(companies) else ""
        location = unescape(locations[i]).strip() if i < len(locations) else ""

        # Build full URL
        if url_path.startswith("/"):
            url = f"https://{domain}{url_path}"
        else:
            url = f"https://{domain}/{url_path}"

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "country": country,
            "skill": skill,
        })

    return jobs


class IndeedBoard(Board):
    """Scrapes Indeed across 12+ country domains for remote jobs."""

    name = "indeed"
    label = "Indeed (multi-country)"

    async def fetch(self, limit: int = 200) -> list[Job]:
        all_jobs: list[Job] = []
        seen: set[str] = set()

        # Build URL tasks — international domains first, US last
        # This ensures international jobs aren't crowded out by US volume
        international = []
        us_tasks = []
        for domain, country, skills in COUNTRIES:
            for skill in skills[:3]:
                for page in range(MAX_PAGES):
                    start = page * 10
                    url = _build_url(domain, skill, start)
                    entry = (url, domain, country, skill)
                    if domain == "www.indeed.com":
                        us_tasks.append(entry)
                    else:
                        international.append(entry)
        tasks = international + us_tasks

        # Process in batches of 5 concurrent requests
        batch_size = 5
        for i in range(0, len(tasks), batch_size):
            if len(all_jobs) >= limit:
                break

            batch = tasks[i:i + batch_size]
            results = await asyncio.gather(
                *[
                    asyncio.to_thread(get_cf, url, 12.0, "safari")
                    for url, _, _, _ in batch
                ],
                return_exceptions=True,
            )

            for (url, domain, country, skill), result in zip(batch, results):
                if isinstance(result, Exception) or not result:
                    continue

                try:
                    jobs = _extract_jobs(result, domain, country, skill)
                except Exception:
                    continue

                for job in jobs:
                    # Deduplicate by title + company
                    key = f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"
                    if key in seen:
                        continue
                    seen.add(key)

                    # All jobs from /remote-*-jobs paths are remote
                    loc = job["location"]
                    remote = "Remote"
                    # Use "Remote" as location for eligibility, keep original for display
                    display_loc = loc if loc else f"Remote ({job['country']})"

                    all_jobs.append(Job(
                        title=job["title"],
                        company=job["company"],
                        url=job["url"],
                        board=self.name,
                        location="Remote",
                        remote=remote,
                        tags=f"{job['skill']} {job['country']}",
                        description=f"Indeed {job['country']}: {job['title']} at {job['company']}",
                        posted_at="",
                        eligible_countries=[],
                    ))

                    if len(all_jobs) >= limit:
                        break

        return all_jobs
