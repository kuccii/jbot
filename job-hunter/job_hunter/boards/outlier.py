"""Outlier — AI training freelance jobs from outlier.ai.

Scrapes the sitemap to discover all language and expert category pages,
then fetches each page to extract the job title, pay rate, and apply URL.

Pages found in sitemap:
  - 79 language pages (e.g. /languages/pl-pl, /languages/en-gb)
  - 18 expert category pages (e.g. /experts/cs, /experts/ml)

Each page has a structured job listing with:
  - Title from og:title (e.g. "Polish Freelance STEM Writing – Up to $15/hr")
  - Pay rate extracted from title
  - Apply URL: https://app.outlier.ai/login?job_post_id=XXXXX
"""

from __future__ import annotations

import asyncio
import re
import json

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job, AUDIENCE_ENTRY

SITEMAP_URL = "https://outlier.ai/sitemap.xml"
APPLY_BASE = "https://app.outlier.ai"

# Languages relevant to Rwandan job seekers.
# Rwanda's official languages: English, French, Kinyarwanda.
# Regional languages: Kiswahili (East African Community).
# Additional: Hindi/Urdu has a large diaspora in East Africa.
RELEVANT_LANG_CODES = {
    "en", "en-gb", "en-us", "en-au",
    "fr", "fr-fr", "fr-be", "fr-ca",
    "sw", "sw-ke", "sw-tz",  # Kiswahili
    "rw",  # Kinyarwanda
}

# Expert categories accessible without a PhD or specialized degree.
RELEVANT_EXPERT_CATEGORIES = {
    "cs",  # computer science — general coding
    "ml",  # machine learning — if they have skills
    "design",  # design
    "video-creators",  # video creation
    "statistics",  # statistics
    "cybersecurity-r70x9k2",
    "cybersecurity-r150v8m",
    "cybersecurity-r100q4z",
}

# Titles that require specialized degrees/expertise NOT accessible to entry-level.
REJECT_TITLE_PATTERNS = [
    r"phd",
    r"cardiology",
    r"medical",
    r"quant finance",
    r"quant finance",
    r"finance experts in india",
    r"finance experts in",
    r"law-sgp",
]

# Languages that Rwandans typically don't speak.
# Only English, French, and Kiswahili are relevant for Rwanda.
NON_RELEVANT_LANGUAGES = {
    # European
    "danish", "finnish", "flemish", "norwegian", "swedish",
    "dutch", "german", "italian", "portuguese", "spanish",
    "polish", "czech", "hungarian", "romanian", "bulgarian",
    "croatian", "serbian", "slovak", "slovenian", "estonian",
    "latvian", "lithuanian", "turkish", "greek", "ukrainian",
    "kazakh", "russian",
    # East Asian
    "japanese", "korean", "chinese", "mandarin", "cantonese",
    # Southeast Asian
    "thai", "vietnamese", "indonesian", "malay", "filipino", "tagalog",
    # South Asian
    "hindi", "bengali", "tamil", "telugu", "marathi", "gujarati",
    "punjabi", "urdu", "kannada",
    # Middle Eastern
    "arabic", "hebrew", "persian",
}


def _is_relevant(title: str, url: str) -> bool:
    """Filter Outlier jobs to only those accessible to Rwandan job seekers."""
    title_lower = title.lower()
    
    # Reject specialized/expert jobs
    for pattern in REJECT_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            return False
    
    # For language pages: only keep relevant languages
    lang_match = re.search(r"/languages/([a-z]{2}(?:-[a-z]{2})?)", url)
    if lang_match:
        lang_code = lang_match.group(1)
        if lang_code in RELEVANT_LANG_CODES:
            return True
        # Check if title mentions a non-relevant language
        for lang in NON_RELEVANT_LANGUAGES:
            if lang in title_lower:
                return False
        # If we can't identify the language, keep it (might be English)
        return True
    
    # For expert pages: only keep relevant categories
    expert_match = re.search(r"/experts/([a-z-]+)", url)
    if expert_match:
        category = expert_match.group(1)
        if category in RELEVANT_EXPERT_CATEGORIES:
            return True
        # Reject highly specialized categories (medicine, law, etc.)
        return False
    
    return True


class OutlierBoard(Board):
    """Scrapes AI training job listings from Outlier language/expert pages."""

    name = "outlier"
    label = "Outlier — AI Training ($15-50/hr, Remote Worldwide)"

    async def fetch(self, limit: int = 100) -> list[Job]:
        # Step 1: Get all page URLs from sitemap
        async with self.client() as client:
            resp = await get(client, SITEMAP_URL)
            sitemap_text = resp.text

        lang_urls = re.findall(
            r"<loc>(https://outlier\.ai/languages/[^<]+)</loc>", sitemap_text
        )
        expert_urls = re.findall(
            r"<loc>(https://outlier\.ai/experts/[^<]+)</loc>", sitemap_text
        )
        all_urls = lang_urls + expert_urls

        if not all_urls:
            return []

        # Step 2: Fetch each page concurrently (bounded concurrency)
        sem = asyncio.Semaphore(10)

        async def _fetch_one(client, url: str) -> tuple[Job | None, str]:
            async with sem:
                try:
                    resp = await get(client, url)
                    return self._parse_page(url, resp.text), url
                except Exception:
                    return None, url

        async with self.client() as client:
            results = await asyncio.gather(
                *(_fetch_one(client, u) for u in all_urls)
            )

        jobs = [j for j, _ in results if j is not None]

        # Filter to only jobs accessible to Rwandan job seekers
        filtered = []
        for job, source_url in results:
            if job and _is_relevant(job.title, source_url):
                filtered.append(job)
        jobs = filtered

        # Deduplicate by title
        seen = set()
        unique: list[Job] = []
        for j in jobs:
            key = j.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(j)

        return unique[:limit]

    def _parse_page(self, url: str, html: str) -> Job | None:
        """Extract job info from an Outlier language or expert page."""
        # Title from og:title — format: "Polish Freelance STEM Writing – Up to $15/hr | Outlier AI"
        og_title = re.search(
            r'<meta property="og:title" content="([^"]+)"', html
        )
        if not og_title:
            return None

        raw_title = og_title.group(1).strip()
        # Strip " | Outlier AI" suffix
        title = re.sub(r"\s*\|\s*Outlier AI\s*$", "", raw_title).strip()

        if not title or "Train the Next Generation" in title:
            return None  # Generic homepage title, not a real job

        # Extract pay rate from title: "Up to $15/hr" or "$15-50/hr"
        pay_match = re.search(r"\$(\d+)(?:-(\d+))?\s*(?:USD)?/hr", title)
        pay = pay_match.group(0) if pay_match else ""

        # Extract apply URL with job_post_id
        apply_match = re.search(
            r'href="(https?://app\.outlier\.ai/login\?job_post_id=\d+)"', html
        )
        apply_url = apply_match.group(1) if apply_match else APPLY_BASE

        # Extract language from URL path
        lang_match = re.search(r"/languages/([a-z]{2}(?:-[a-z]{2})?)", url)
        expert_match = re.search(r"/experts/([a-z-]+)", url)

        if lang_match:
            lang_code = lang_match.group(1)
            source = f"Language: {lang_code}"
        elif expert_match:
            source = f"Expert: {expert_match.group(1)}"
        else:
            source = url

        # Extract description from page content
        desc_match = re.search(
            r'<meta property="og:description" content="([^"]+)"', html
        )
        description = desc_match.group(1) if desc_match else f"{title} — {source}"

        # Build description with pay and source info
        full_desc = f"Platform: Outlier AI (Scale AI)\n{title}\nPay: {pay}\nSource: {source}\nApply: {apply_url}"

        return Job(
            title=title,
            company="Outlier",
            url=apply_url,
            board=self.name,
            location="Remote Worldwide",
            remote="Remote",
            tags=f"ai-training {source}",
            description=full_desc,
            posted_at="",
            eligible_countries=[],
            audience=AUDIENCE_ENTRY,
        )
