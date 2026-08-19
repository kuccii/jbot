"""Indeed.com board — generates direct search links.

Indeed blocks all scraping (403 on curl_cffi, Playwright, and RSS).
Instead of scraping, this board generates curated search URLs that
users can click to browse Indeed directly.

Searches are configured for Rwanda-friendly remote jobs with relevant
keywords. Each entry is a pre-built Indeed search URL.
"""

from __future__ import annotations

from job_hunter.boards.base import Board
from job_hunter.models import Job


# Pre-built Indeed search URLs for Rwanda-friendly remote jobs.
# Each entry targets specific keywords and locations.
SEARCH_QUERIES: list[dict] = [
    {
        "title": "Remote Python Developer",
        "query": "remote python developer",
        "location": "",
        "tags": "python,developer,remote",
    },
    {
        "title": "Remote Software Engineer",
        "query": "remote software engineer",
        "location": "",
        "tags": "engineering,software,remote",
    },
    {
        "title": "Remote Data Scientist",
        "query": "remote data scientist",
        "location": "",
        "tags": "data,science,ml,remote",
    },
    {
        "title": "Remote AI/ML Engineer",
        "query": "remote AI machine learning engineer",
        "location": "",
        "tags": "ai,ml,engineering,remote",
    },
    {
        "title": "Remote Full Stack Developer",
        "query": "remote full stack developer",
        "location": "",
        "tags": "fullstack,javascript,react,remote",
    },
    {
        "title": "Remote DevOps Engineer",
        "query": "remote devops engineer",
        "location": "",
        "tags": "devops,cloud,infrastructure,remote",
    },
    {
        "title": "Remote Product Manager",
        "query": "remote product manager",
        "location": "",
        "tags": "product,management,remote",
    },
    {
        "title": "Remote UX Designer",
        "query": "remote UX designer",
        "location": "",
        "tags": "ux,design,ui,remote",
    },
    {
        "title": "Remote Data Analyst",
        "query": "remote data analyst",
        "location": "",
        "tags": "data,analysis,sql,remote",
    },
    {
        "title": "Remote Content Writer",
        "query": "remote content writer",
        "location": "",
        "tags": "writing,content,remote",
    },
    {
        "title": "Remote Customer Support",
        "query": "remote customer support",
        "location": "",
        "tags": "support,customer,remote",
    },
    {
        "title": "Remote Virtual Assistant",
        "query": "remote virtual assistant",
        "location": "",
        "tags": "assistant,admin,remote",
    },
    {
        "title": "Worldwide Freelance Developer",
        "query": "freelance developer worldwide",
        "location": "",
        "tags": "freelance,developer,worldwide",
    },
    {
        "title": "Africa Remote Jobs",
        "query": "remote jobs africa",
        "location": "",
        "tags": "africa,remote,jobs",
    },
]


def _build_indeed_url(query: str, location: str = "") -> str:
    """Build an Indeed search URL."""
    base = "https://www.indeed.com/jobs"
    params = f"?q={query.replace(' ', '+')}"
    if location:
        params += f"&l={location.replace(' ', '+')}"
    else:
        params += "&l="  # Remote/worldwide
    return base + params


class IndeedBoard(Board):
    """Generates direct Indeed search links for remote jobs."""

    name = "indeed"
    label = "Indeed.com (direct search links)"

    async def fetch(self, limit: int = 30) -> list[Job]:
        jobs: list[Job] = []

        for item in SEARCH_QUERIES[:limit]:
            url = _build_indeed_url(item["query"], item.get("location", ""))

            jobs.append(Job(
                title=f"🔍 {item['title']}",
                company="Indeed.com",
                url=url,
                board=self.name,
                location="Worldwide",
                remote="Remote",
                tags=item["tags"],
                description=(
                    f"Search Indeed for: {item['query']}\n"
                    f"Click the link to browse live job listings on Indeed.com.\n"
                    f"Indeed blocks automated scraping, so this is a direct search link."
                ),
                posted_at="",
                eligible_countries=[],
            ))

        return jobs
