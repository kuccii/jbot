"""We Work Remotely — https://weworkremotely.com

Server-rendered listing of remote jobs. Job entries carry a `region` value
like "Anywhere in the World", "Europe", "USA only", "Africa", "EMEA" —
exactly what the eligibility filter needs.

Note: the site sometimes returns 403 to datacenter IPs; that failure is
logged and the rest of discovery continues.
"""

from __future__ import annotations

from html import unescape

from bs4 import BeautifulSoup

from job_hunter.boards.base import Board
from job_hunter.fetch import get
from job_hunter.models import Job

LIST_URL = "https://weworkremotely.com/remote-jobs"


class WeWorkRemotelyBoard(Board):
    name = "weworkremotely"
    label = "WeWorkRemotely (worldwide remote)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        async with self.client() as client:
            resp = await get(client, LIST_URL)
            soup = BeautifulSoup(resp.text, "html.parser")

        jobs: list[Job] = []
        # Entries live in <li class="feature"> / <li class="job"> with a link.
        for li in soup.select("li.feature, li.job"):
            a = li.find("a", href=True)
            if not a:
                continue
            title = _text(a.select_one("span.title"))
            if not title:
                continue
            region = _text(a.select_one("span.region"))
            jobs.append(Job(
                title=unescape(title),
                company=unescape(_text(a.select_one("span.company"))),
                url="https://weworkremotely.com" + a["href"],
                board=self.name,
                location=region,
                remote="Remote",
                description="",
                posted_at=_text(a.select_one("time")) or _text(a.select_one("span.date")),
            ))
            if len(jobs) >= limit:
                break
        return jobs


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""
