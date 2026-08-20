"""meetfrank.com board — extracts jobs from Apollo cache via __NEXT_DATA__."""

import asyncio
import json
import re
from datetime import datetime, timezone

from job_hunter.boards.base import Board
from job_hunter.fetch import get_cf
from job_hunter.models import Job


class MeetFrankBoard(Board):
    name = "meetfrank"
    label = "MeetFrank"

    _BASE = "https://www.meetfrank.com"

    async def fetch(self, limit: int = 50) -> list[Job]:
        jobs: list[Job] = []

        # The /search page returns jobs for Rwanda in the Apollo cache
        html = await asyncio.to_thread(get_cf, f"{self._BASE}/search", 15.0, "safari")
        if html:
            jobs.extend(self._parse_next_data(html))

        # Also try /remote-jobs
        html2 = await asyncio.to_thread(get_cf, f"{self._BASE}/remote-jobs", 15.0, "safari")
        if html2:
            jobs.extend(self._parse_next_data(html2))

        return jobs[:limit]

    def _parse_next_data(self, html: str) -> list[Job]:
        """Extract job entries from __NEXT_DATA__ Apollo cache."""
        jobs: list[Job] = []
        seen_ids: set[str] = set()

        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html, re.DOTALL,
        )
        if not match:
            return jobs

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return jobs

        cache = (
            data.get("props", {})
            .get("pageProps", {})
            .get("apollo", {})
            .get("cache", {})
        )
        if not cache:
            return jobs

        # Extract all job-like entries from Apollo cache
        for key, entry in cache.items():
            if not isinstance(entry, dict):
                continue

            typename = entry.get("__typename", "")
            if typename not in (
                "PaidOpeningWithSnippetsType",
                "NonPaidOpeningType",
            ):
                continue

            job_id = entry.get("id", "")
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = entry.get("title", "")
            url_handle = entry.get("urlHandle", "")
            published = entry.get("publishedAt", "")

            if not title:
                continue

            # Build URL
            url = f"{self._BASE}/job/{url_handle}" if url_handle else ""

            # Extract company — follow Apollo refs:
            # Job.company -> {__ref: "CompanyType:xxx"}
            #   -> CompanyType.profile -> {__ref: "CompanyProfileType:yyy"}
            #     -> CompanyProfileType.name
            company = ""
            company_ref = entry.get("company")
            if isinstance(company_ref, dict):
                ref = company_ref.get("__ref", "")
                if ref and ref in cache:
                    company_obj = cache[ref]
                    # Follow profile ref to get name
                    profile_ref = company_obj.get("profile")
                    if isinstance(profile_ref, dict):
                        pre = profile_ref.get("__ref", "")
                        if pre and pre in cache:
                            company = cache[pre].get("name", "")
                    if not company:
                        company = company_obj.get("urlHandle", "")
            elif isinstance(company_ref, str) and company_ref in cache:
                company = cache[company_ref].get("name", "")

            # Remote type
            remote_data = entry.get("remote", {})
            remote_type = ""
            allowed_places = []
            if isinstance(remote_data, dict):
                remote_type = remote_data.get("type", "")
                allowed_places = [
                    p.get("name", "")
                    for p in remote_data.get("allowedPlaces", [])
                    if isinstance(p, dict)
                ]

            # Salary
            salary = entry.get("salaryRange") or ""
            if isinstance(salary, dict):
                salary = f"{salary.get('min', '')} - {salary.get('max', '')} {salary.get('currency', '')}"

            j = Job(
                title=title,
                company=company,
                url=url,
                board=self.name,
            )
            j.posted_at = published[:10] if published else None
            if allowed_places:
                j.location = ", ".join(allowed_places)
            elif remote_type == "FULLY":
                j.location = "Remote"
            else:
                j.location = remote_type
            j.description = f"Remote: {remote_type}" if remote_type else ""
            if salary:
                j.description += f" | Salary: {salary}" if j.description else f"Salary: {salary}"

            jobs.append(j)

        return jobs
