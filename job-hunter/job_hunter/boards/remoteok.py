"""RemoteOK — https://remoteok.com

Public JSON API (no key required): GET https://remoteok.com/api
Skill-tag feeds (e.g. `?tag=python`) return curated, relevant remote jobs.
We fetch those first and only fall back to the unfiltered general feed to
fill the remaining quota.
"""

from __future__ import annotations

from html import unescape

from job_hunter.boards.base import Board
from job_hunter.boards.utils import strip_html, remote_status
from job_hunter.fetch import get
from job_hunter.models import Job

API_URL = "https://remoteok.com/api"


class RemoteOKBoard(Board):
    name = "remoteok"
    label = "RemoteOK (worldwide remote)"

    def __init__(self, transport=None, tags: list[str] | None = None):
        super().__init__(transport)
        # Candidate skill tags from the user's config keywords.
        self.tags = [t.strip().lower() for t in (tags or []) if t.strip()][:5]

    async def fetch(self, limit: int = 30) -> list[Job]:
        # Skill-tag feeds first (relevant), general feed last (fill the quota).
        urls = [f"{API_URL}?tag={t}" for t in self.tags] + [API_URL]
        jobs: list[Job] = []
        seen: set[str] = set()

        async with self.client() as client:
            for url in urls:
                try:
                    resp = await get(client, url)
                    data = resp.json()
                except Exception:
                    continue  # one failing feed must not kill the board

                for item in data:
                    if not isinstance(item, dict) or "position" not in item:
                        continue  # skip the metadata header object
                    title = unescape(str(item.get("position", "")))
                    if not title:
                        continue
                    link = item.get("url") or item.get("apply_url") or ""
                    if link in seen:
                        continue
                    seen.add(link)
                    loc = unescape(str(item.get("location", "")))
                    jobs.append(Job(
                        title=title,
                        company=unescape(str(item.get("company", ""))),
                        url=link,
                        board=self.name,
                        location=loc,
                        remote=remote_status(loc),
                        tags=", ".join(item.get("tags") or []),
                        description=strip_html(item.get("description", "")),
                        posted_at=str(item.get("date", "")),
                    ))
                    if len(jobs) >= limit:
                        return jobs
        return jobs
