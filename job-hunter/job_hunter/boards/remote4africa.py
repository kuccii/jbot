"""Remote4Africa — https://remote4africa.com

Server-rendered job board for African talent. Each job detail page embeds a
schema.org JobPosting JSON-LD block that includes `applicantLocationRequirements`
— an explicit list of countries the employer can hire from. We use that list
to decide Rwanda eligibility with certainty.

The list page is scraped for job links, then each detail page is fetched for
its JSON-LD. To be polite, we cap how many detail pages we open per run.
"""

from __future__ import annotations

import asyncio
import json
import re
from html import unescape

from bs4 import BeautifulSoup

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

# The /remote-jobs/rw page is Remote4Africa's Rwanda-targeted feed.
# The employer's applicantLocationRequirements on each detail page is still
# checked as the authoritative Rwanda-eligibility signal.
LIST_URL = "https://remote4africa.com/remote-jobs/rw"
JOB_LINK_RE = re.compile(r"/jobs/([^/?#]+)")
DETAIL_LIMIT = 25  # cap on detail-page fetches per run


class Remote4AfricaBoard(Board):
    name = "remote4africa"
    label = "Remote4Africa (Africa jobs, Rwanda in country list)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        all_slugs: list[str] = []

        async with self.client() as client:
            # Paginate through listing pages until we have enough slugs or
            # reach the detail-page cap.
            page = 1
            while len(all_slugs) < max(1, min(limit, DETAIL_LIMIT)):
                url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
                try:
                    resp = await get(client, url)
                    soup = BeautifulSoup(resp.text, "html.parser")
                except Exception:
                    break

                page_slugs: list[str] = []
                for a in soup.find_all("a", href=True):
                    m = JOB_LINK_RE.search(a["href"])
                    if m and "create" not in a["href"] and m.group(1) not in all_slugs:
                        page_slugs.append(m.group(1))

                if not page_slugs:
                    break  # no more pages
                all_slugs.extend(page_slugs)
                page += 1

            jobs: list[Job] = []
            sem = asyncio.Semaphore(4)
            async def _fetch_one(slug: str) -> Job | None:
                async with sem:
                    try:
                        return await self._job_from_detail(client, slug)
                    except Exception:
                        return None

            for slug in all_slugs[: max(1, min(limit, DETAIL_LIMIT))]:
                job = await _fetch_one(slug)
                if job:
                    jobs.append(job)
                    if len(jobs) >= limit:
                        break
            return jobs

    async def _job_from_detail(self, client, slug: str) -> Job | None:
        resp = await get(client, f"https://remote4africa.com/jobs/{slug}")
        soup = BeautifulSoup(resp.text, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (ValueError, TypeError):
                continue
            if data.get("@type") != "JobPosting":
                continue
            return self._from_job_posting(data, slug)

        # No JobPosting JSON-LD (error/captcha/redirect page) -> skip it.
        # We only store jobs whose eligibility we can actually verify.
        return None

    def _from_job_posting(self, data: dict, slug: str) -> Job:
        org = data.get("hiringOrganization") or {}
        location = data.get("jobLocation") or {}
        address = location.get("address") or {}
        locality = address.get("addressLocality") or ""
        countries = []
        for req in data.get("applicantLocationRequirements") or []:
            name = (req or {}).get("name")
            if name:
                countries.append(name)
        salary = data.get("baseSalary") or {}
        salary_text = ""
        if isinstance(salary, dict):
            value = salary.get("value") or {}
            if isinstance(value, dict) and value.get("value"):
                salary_text = f"{value.get('value')} {value.get('currency', '')}".strip()
        desc = BeautifulSoup(
            data.get("description") or "", "html.parser"
        ).get_text(" ", strip=True)[:2000]
        return Job(
            title=data.get("title") or slug.replace("-", " ").title(),
            company=org.get("name") or "",
            url=data.get("url") or f"https://remote4africa.com/jobs/{slug}",
            board=self.name,
            location=locality or (", ".join(countries) if countries else ""),
            remote="Remote" if data.get("jobLocationType") == "TELECOMMUTE" else "",
            description=desc,
            posted_at=str(data.get("datePosted", "")),
            eligible_countries=countries,
        )
