"""RemoteOK Entry-Level — customer support, VA, admin, ops jobs.

RemoteOK has a public JSON API with skill-tagged feeds. This board
scrapes entry-level categories specifically:

  - customer support (62+ jobs)
  - virtual assistant (24+ jobs)
  - admin (15+ jobs)
  - ops (57+ jobs)
  - sales (41+ jobs)
  - hr (14+ jobs)
  - content writing (15+ jobs)
  - education (50+ jobs)

These are tagged audience=entry or audience=creative as appropriate.
"""

from __future__ import annotations

from html import unescape

from job_hunter.boards.base import Board
from job_hunter.boards.utils import strip_html, remote_status
from job_hunter.fetch import get
from job_hunter.models import Job, AUDIENCE_ENTRY, AUDIENCE_CREATIVE

API_URL = "https://remoteok.com/api"

# Entry-level tag categories and their audience tags.
ENTRY_TAGS = {
    # Entry-level (no degree required)
    "customer support": AUDIENCE_ENTRY,
    "virtual assistant": AUDIENCE_ENTRY,
    "admin": AUDIENCE_ENTRY,
    "ops": AUDIENCE_ENTRY,
    "hr": AUDIENCE_ENTRY,
    "sales": AUDIENCE_ENTRY,
    "recruiter": AUDIENCE_ENTRY,
    "travel": AUDIENCE_ENTRY,
    # Creative
    "content writing": AUDIENCE_CREATIVE,
    "education": AUDIENCE_ENTRY,
    "design": AUDIENCE_CREATIVE,
    "marketing": AUDIENCE_CREATIVE,
}


class RemoteOKEntryBoard(Board):
    """Scrapes RemoteOK for entry-level/VA/CX/admin/ops jobs."""

    name = "remoteok_entry"
    label = "RemoteOK Entry-Level (VA, CS, Admin, Ops)"

    async def fetch(self, limit: int = 500) -> list[Job]:
        jobs: list[Job] = []
        seen: set[str] = set()

        # Fetch the main API and filter by entry-level tags
        async with self.client() as client:
            try:
                resp = await get(client, API_URL)
                data = resp.json()
            except Exception:
                return []

            for item in data:
                if not isinstance(item, dict) or "position" not in item:
                    continue

                title = unescape(str(item.get("position", "")))
                if not title:
                    continue

                tags = [t.strip().lower() for t in (item.get("tags") or [])]

                # Check if this job matches any entry-level tag
                audience = None
                for tag in tags:
                    if tag in ENTRY_TAGS:
                        audience = ENTRY_TAGS[tag]
                        break

                if not audience:
                    continue  # Skip non-entry-level jobs

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
                    tags=", ".join(tags),
                    description=strip_html(item.get("description", "")),
                    posted_at=str(item.get("date", "")),
                    eligible_countries=[],
                    audience=audience,
                ))

                if len(jobs) >= limit:
                    break

        return jobs
