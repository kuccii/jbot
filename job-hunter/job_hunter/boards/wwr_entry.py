"""WeWorkRemotely Entry-Level — customer support, admin, entry jobs.

Scrapes the /categories/remote-customer-support-jobs page which has
39+ entry-level remote jobs. Extracts data directly from the listing
page HTML.
"""

from __future__ import annotations

import asyncio
import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get_cf
from job_hunter.models import Job, AUDIENCE_ENTRY

BASE_URL = "https://www.weworkremotely.com"

# Category pages to scrape
CATEGORIES = [
    "/categories/remote-customer-support-jobs",
    "/categories/remote-admin-jobs",
]

# Entry-level tag keywords
ENTRY_KEYWORDS = [
    "customer support", "customer service", "technical support",
    "virtual assistant", "administrative", "admin", "data entry",
    "transcription", "moderation", "content moderator",
    "help desk", "service desk", "receptionist", "coordinator",
    "bookkeeper", "accounts payable", "billing",
    "social media", "content writing", "copywriter",
    "proofreader", "scheduler", "dispatcher", "sales representative",
    "inbound sales", "outbound sales", "account manager",
]


def _is_entry_level(title: str) -> bool:
    """Check if a job is entry-level based on title."""
    text = title.lower()
    return any(kw in text for kw in ENTRY_KEYWORDS)


def _extract_from_listing(html: str, category: str) -> list[dict]:
    """Extract job data from the WWR listing page."""
    jobs = []

    # WWR structure: <a class="listing-link--unlocked" href="/remote-jobs/slug">
    #   <span class="new-listing__header__title__text">Title</span>
    # Company is in tooltip: <span class="tooltip--flag-logo__tooltiptext">View Company Profile</span>
    # Company slug is in the URL: /company/slug

    # Extract job links with their titles
    pattern = r'<a[^>]*href="(/remote-jobs/[^"]+)"[^>]*>.*?<span[^>]*class="new-listing__header__title__text"[^>]*>(.*?)</span>'
    matches = re.findall(pattern, html, re.DOTALL)

    for link, title_html in matches:
        if "plan" in link or "utm" in link:
            continue

        title = re.sub(r'<[^>]+>', '', unescape(title_html)).strip()
        if not title:
            continue

        # Extract company from slug: /remote-jobs/company-slug-job-title
        # The slug format is: company-name-job-title
        slug = link.split("/")[-1] if "/" in link else link
        # Company is usually the first part before the job title
        # We'll try to find it from the HTML context

        # Find company name from the tooltip area near this link
        # Look for /company/slug pattern near this link
        company_match = re.search(
            rf'href="/company/([^"]+)"[^>]*>.*?</a>.*?{re.escape(link)}',
            html, re.DOTALL,
        )
        company = ""
        if company_match:
            company = company_match.group(1).replace("-", " ").title()
        else:
            # Try reverse order: link first, then company
            company_match = re.search(
                rf'{re.escape(link)}.*?href="/company/([^"]+)"',
                html, re.DOTALL,
            )
            if company_match:
                company = company_match.group(1).replace("-", " ").title()

        # Extract region from the listing
        region_match = re.search(
            rf'{re.escape(link)}.*?Anywhere in the World|United States|Europe|Global',
            html, re.DOTALL,
        )
        region = region_match.group(0)[-30:] if region_match else "Remote"

        jobs.append({
            "title": title,
            "company": company,
            "url": f"{BASE_URL}{link}",
            "region": region,
        })

    return jobs


class WWREntryBoard(Board):
    """Scrapes WeWorkRemotely for entry-level customer support/admin jobs."""

    name = "wwr_entry"
    label = "WeWorkRemotely Entry-Level (CS, Admin)"

    async def fetch(self, limit: int = 500) -> list[Job]:
        all_jobs: list[Job] = []
        seen: set[str] = set()

        for category in CATEGORIES:
            url = f"{BASE_URL}{category}"
            try:
                html = await asyncio.to_thread(get_cf, url, 12.0, "safari")
                if not html:
                    continue

                jobs = _extract_from_listing(html, category)

                for job in jobs:
                    title = job["title"]
                    if not _is_entry_level(title):
                        continue

                    key = f"{title.lower().strip()}|{job['company'].lower().strip()}"
                    if key in seen:
                        continue
                    seen.add(key)

                    all_jobs.append(Job(
                        title=title,
                        company=job["company"],
                        url=job["url"],
                        board=self.name,
                        location="Remote",
                        remote="Remote",
                        tags=f"weworkremotely {category.split('/')[-1].replace('remote-', '').replace('-jobs', '')}",
                        description=f"WeWorkRemotely: {title} at {job['company']}",
                        posted_at="",
                        eligible_countries=[],
                        audience=AUDIENCE_ENTRY,
                    ))

                    if len(all_jobs) >= limit:
                        break
            except Exception:
                continue
            await asyncio.sleep(1.0)

        return all_jobs
