"""startup.jobs board — parses remote job listing pages via curl_cffi Safari."""

import asyncio
import re
from datetime import datetime, timezone

from job_hunter.boards.base import Board
from job_hunter.fetch import get_cf
from job_hunter.models import Job


class StartupJobsBoard(Board):
    name = "startupjobs"
    label = "Startup Jobs"

    _BASE = "https://startup.jobs"

    async def fetch(self, limit: int = 50) -> list[Job]:
        jobs: list[Job] = []
        page = 1

        while len(jobs) < limit and page <= 5:
            url = f"{self._BASE}/remote-jobs" if page == 1 else f"{self._BASE}/remote-jobs?page={page}"
            html = await asyncio.to_thread(get_cf, url, 15.0, "safari")
            if not html:
                break

            page_jobs = self._parse_listing(html)
            if not page_jobs:
                break

            jobs.extend(page_jobs)
            page += 1

        return jobs[:limit]

    def _parse_listing(self, html: str) -> list[Job]:
        """Extract jobs from the listing page HTML."""
        jobs: list[Job] = []
        seen_urls: set[str] = set()

        # Find all anchors with long slugs (job posts, not navigation)
        all_links = re.findall(
            r'<a[^>]*href="(/[^"]{20,})"[^>]*>(.*?)</a>',
            html, re.DOTALL,
        )

        # Navigation words to skip
        skip = {
            "Remote jobs", "Part-time jobs", "Internships", "Startup Jobs",
            "Load next page…", "Set up job preferences →", "Browse Markets",
            "Post a Job", "Log in", "Advertise", "Pricing",
        }

        current_job = None
        for href, text in all_links:
            clean = re.sub(r'<[^>]+>', '', text).strip()
            if not clean or clean in skip:
                continue
            # Skip Mustache templates
            if "{" in clean and "}" in clean:
                continue

            if href.startswith("/company/"):
                # This is a company link — attach to the previous job
                if current_job:
                    current_job["company"] = clean.replace("&amp;", "&")
                    current_job["company_url"] = href
                    # Now we have title + company, create the job
                    url = current_job.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        j = Job(
                            title=current_job["title"].replace("&amp;", "&"),
                            company=current_job.get("company", ""),
                            url=url,
                            board=self.name,
                        )
                        j.location = "Remote"
                        j.description = f"Startup: {current_job.get('company', '')}"
                        jobs.append(j)
                    current_job = None
            elif (
                "/company/" not in href
                and not href.startswith(("/remote", "/part-time", "/intern", "/talent", "/markets", "/login", "/pricing", "/advertise", "/landing"))
            ):
                current_job = {
                    "title": clean.replace("&amp;", "&"),
                    "url": f"{self._BASE}{href}",
                }

        return jobs
