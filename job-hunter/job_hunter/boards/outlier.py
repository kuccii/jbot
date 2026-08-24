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

        async def _fetch_one(client, url: str) -> Job | None:
            async with sem:
                try:
                    resp = await get(client, url)
                    return self._parse_page(url, resp.text)
                except Exception:
                    return None

        async with self.client() as client:
            results = await asyncio.gather(
                *(_fetch_one(client, u) for u in all_urls)
            )

        jobs = [j for j in results if j is not None]

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
