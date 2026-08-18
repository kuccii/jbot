"""Persona Talent — https://apply.personatalent.com/jobs

Managed recruiting/staffing agency hiring remote professionals for client
companies (support, ops, finance, sales, marketing, CX, plus some senior
tech roles).

The jobs directory is server-rendered HTML — no JavaScript required — and
every posting carries an explicit location badge, almost always
"Remote (Worldwide)", which makes Rwanda eligibility deterministic.

Scraped page: GET https://apply.personatalent.com/jobs
Each listing is an <a href="/j/..."> card containing:
  <span class="...locationBadge...">Remote (Worldwide)</span>
  <h3 class="...cardTitle...">Sales Development Representative</h3>
  <p class="...cardSummary...">We are looking for ...</p>
"""

from __future__ import annotations

import re
from html import unescape

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

JOBS_URL = "https://apply.personatalent.com/jobs"

# A listing card is an <a href="/j/...">...</a> block. CSS-module class
# suffixes (e.g. `cardLink__07w0Y`) change between builds, so match on the
# href and the stable class prefixes only.
_CARD_RE = re.compile(r'<a[^>]*href="(/j/[^"]+)"[^>]*>(.*?)</a>', re.S)
_TITLE_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S)
_BADGE_RE = re.compile(r"Remote\s*\((.*?)\)", re.S)
_SUMMARY_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)


def _strip_html(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


class PersonaBoard(Board):
    name = "persona"
    label = "Persona Talent (staffing agency, all Remote Worldwide)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        jobs: list[Job] = []
        async with self.client() as client:
            try:
                resp = await get(client, JOBS_URL)
                html = resp.text
            except Exception:
                return jobs

            for href, body in _CARD_RE.findall(html):
                title = _strip_html(_TITLE_RE.search(body).group(1)) if _TITLE_RE.search(body) else ""
                if not title:
                    continue

                badge = ""
                m = _BADGE_RE.search(body)
                if m:
                    badge = _strip_html(m.group(1))

                summary = ""
                m = _SUMMARY_RE.search(body)
                if m:
                    summary = _strip_html(m.group(1))

                location = badge if badge else "Worldwide"
                jobs.append(Job(
                    title=title,
                    company="Persona Talent",
                    url=f"https://apply.personatalent.com{href}",
                    board=self.name,
                    location=location,
                    remote="Remote" if "worldwide" in location.lower() else "",
                    tags="",
                    description=summary,
                    posted_at="",
                    eligible_countries=[],
                ))
                if len(jobs) >= limit:
                    break

        return jobs
