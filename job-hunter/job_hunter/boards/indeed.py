"""Indeed.com multi-country scraper — scrapes 19 country domains.

Indeed blocks Chrome/Firefox impersonation but allows Safari. We use
curl_cffi with Safari impersonation to scrape job listings from multiple
country-specific Indeed domains. Each domain uses the /remote-*-jobs
path which returns structured job data.

Sequential requests with 2.5s delays to avoid IP-based rate limits.
Jobs are tagged with audience segments for dashboard filtering.
"""

from __future__ import annotations

import asyncio
import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get_cf
from job_hunter.models import Job, AUDIENCE_TECH, AUDIENCE_ENTRY, AUDIENCE_CREATIVE

# All working Indeed country domains.
COUNTRIES: list[tuple[str, str]] = [
    # Europe (13)
    ("www.indeed.co.uk", "UK"),
    ("www.indeed.de", "Germany"),
    ("www.indeed.nl", "Netherlands"),
    ("www.indeed.ie", "Ireland"),
    ("www.indeed.fr", "France"),
    ("www.indeed.be", "Belgium"),
    ("www.indeed.cz", "Czechia"),
    ("www.indeed.hu", "Hungary"),
    ("www.indeed.no", "Norway"),
    ("www.indeed.fi", "Finland"),
    ("www.indeed.pt", "Portugal"),
    ("www.indeed.es", "Spain"),
    ("www.indeed.ch", "Switzerland"),
    # Americas (2)
    ("www.indeed.com", "US"),
    ("www.indeed.ca", "Canada"),
    # Asia-Pacific (3)
    ("www.indeed.com.au", "Australia"),
    ("www.indeed.sg", "Singapore"),
    ("www.indeed.co.in", "India"),
    # Africa (1)
    ("www.indeed.co.za", "S.Africa"),
]

# Skill categories grouped by audience.
# Each tuple: (skill_slug, audience_tag)
# Kept to ~12 skills so the full run (12 × 19 countries × 1 page) completes in ~5 min.
SKILLS: list[tuple[str, str]] = [
    # ── Tech / Developer (4) ─────────────────────────────────────────
    ("python-developer", AUDIENCE_TECH),
    ("software-engineer", AUDIENCE_TECH),
    ("data-scientist", AUDIENCE_TECH),
    ("machine-learning", AUDIENCE_TECH),
    # ── Entry-Level / Fast Entry — no degree required (10) ───────────
    ("virtual-assistant", AUDIENCE_ENTRY),
    ("data-entry-clerk", AUDIENCE_ENTRY),
    ("customer-support", AUDIENCE_ENTRY),
    ("chat-support", AUDIENCE_ENTRY),
    ("transcriptionist", AUDIENCE_ENTRY),
    ("administrative-assistant", AUDIENCE_ENTRY),
    ("call-center-agent", AUDIENCE_ENTRY),
    ("help-desk", AUDIENCE_ENTRY),
    ("bookkeeper", AUDIENCE_ENTRY),
    ("scheduler", AUDIENCE_ENTRY),
    # ── Creative / Marketing (3) ─────────────────────────────────────
    ("content-writer", AUDIENCE_CREATIVE),
    ("graphic-designer", AUDIENCE_CREATIVE),
    ("social-media-manager", AUDIENCE_CREATIVE),
]

# Pages per skill-country combo (10 jobs per page).
MAX_PAGES = 1

# Delay between requests in seconds. Indeed bans IPs after ~20 rapid requests.
REQUEST_DELAY = 2.5


def _build_url(domain: str, skill: str, start: int = 0) -> str:
    """Build an Indeed country URL using the /remote-*-jobs path."""
    path = f"/remote-{skill}-jobs"
    if start > 0:
        path += f"?start={start}"
    return f"https://{domain}{path}"


def _extract_jobs(html: str, domain: str, country: str, skill: str) -> list[dict]:
    """Extract job data from Indeed HTML."""
    jobs = []

    # Primary: extract from jcs-JobTitle links
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
        urls = re.findall(r'href="(/rc/clk[^"]*)"', html)
        for i, title in enumerate(title_spans):
            url = urls[i] if i < len(urls) else ""
            title_blocks.append((url, unescape(title).strip()))

    # Extract data-jk values for constructing /viewjob URLs
    jk_values = re.findall(r'data-jk="([^"]+)"', html)

    # Extract companies
    companies = re.findall(
        r'data-testid="company-name"[^>]*>([^<]+)<', html
    )
    if not companies:
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

        # Decode HTML entities in URL (e.g. &amp; -> &)
        url_path = unescape(url_path)

        # Use /viewjob?jk= URL if we have the data-jk value (canonical, works in browser)
        if i < len(jk_values):
            url = f"https://{domain}/viewjob?jk={jk_values[i]}"
        elif url_path.startswith("/"):
            url = f"https://{domain}{url_path}"
        else:
            url = f"https://{domain}/{url_path}"

        # Check for visa sponsorship mentions in the title
        title_lower = title.lower()
        has_visa = any(
            kw in title_lower
            for kw in ["visa", "relocation", "sponsor", "work permit"]
        )

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "country": country,
            "skill": skill,
            "visa_sponsorship": has_visa,
        })

    return jobs


class IndeedBoard(Board):
    """Scrapes Indeed across 19 country domains for remote jobs.

    Sequential requests with delays to avoid rate limiting.
    No job limit — scrapes all pages from all countries.
    """

    name = "indeed"
    label = "Indeed (multi-country)"

    async def fetch(self, limit: int = 5000) -> list[Job]:
        all_jobs: list[Job] = []
        seen: set[str] = set()
        rate_limited = 0

        # Build all URL tasks: every skill × every country × every page
        tasks: list[tuple[str, str, str, str, str]] = []
        for domain, country in COUNTRIES:
            for skill, audience in SKILLS:
                for page in range(MAX_PAGES):
                    start = page * 10
                    url = _build_url(domain, skill, start)
                    tasks.append((url, domain, country, skill, audience))

        # Process sequentially with delays to avoid rate limits
        for url, domain, country, skill, audience in tasks:
            if len(all_jobs) >= limit:
                break

            # Stop if we've been rate-limited too many times
            if rate_limited >= 5:
                break

            result = await asyncio.to_thread(get_cf, url, 12.0, "safari")

            if not result:
                rate_limited += 1
                await asyncio.sleep(5.0)
                continue

            # Check for rate limit response
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

            # Delay between requests to avoid rate limiting
            await asyncio.sleep(REQUEST_DELAY)

        return all_jobs
