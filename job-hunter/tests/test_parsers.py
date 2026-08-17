"""Board parser tests using httpx.MockTransport (no network)."""

import json

import httpx
import pytest

from job_hunter.boards.remote4africa import Remote4AfricaBoard
from job_hunter.boards.remoteok import RemoteOKBoard
from job_hunter.boards.weworkremotely import WeWorkRemotelyBoard
from job_hunter.boards.himalayas import HimalayasBoard
from job_hunter.boards.remotive import RemotiveBoard

REMOTE_OK_PAYLOAD = [
    {"_metadata": "ignore me"},
    {
        "position": "Python Engineer",
        "company": "Acme Remote",
        "url": "https://remoteok.com/remote-jobs/python-engineer-acme",
        "location": "🌏",
        "tags": ["python", "backend", "ai"],
        "description": "<p>Build things with Python.</p>",
        "date": "2026-08-17T08:00:03+00:00",
    },
    {
        "position": "Onsite Barista",
        "company": "Coffee Co",
        "url": "https://remoteok.com/remote-jobs/barista",
        "location": "North York, Ontario",
        "tags": [],
        "description": "",
        "date": "",
    },
]

WWR_HTML = """
<html><body>
<section class="jobs">
  <ul>
    <li class="feature">
      <a href="/remote-jobs/django-developer">
        <span class="title">Django Developer</span>
        <span class="company">Global Co</span>
        <span class="region">Anywhere in the World</span>
        <time datetime="2026-08-16">Aug 16</time>
      </a>
    </li>
    <li class="job">
      <a href="/remote-jobs/sales-nyc">
        <span class="title">Sales Rep</span>
        <span class="company">NYC Only Co</span>
        <span class="region">USA only</span>
      </a>
    </li>
  </ul>
</section>
</body></html>
"""

R4A_LISTING_HTML = """
<html><body>
<a href="/jobs/python-ai-engineer-rwanda">Python AI Engineer</a>
<a href="/jobs/senior-net-engineer">Senior .NET Engineer</a>
</body></html>
"""

R4A_DETAIL_HTML = """
<script type="application/ld+json">
{
  "@type": "JobPosting",
  "title": "Python AI Engineer",
  "url": "https://remote4africa.com/jobs/python-ai-engineer-rwanda",
  "datePosted": "2026-08-17T04:26:57Z",
  "jobLocationType": "TELECOMMUTE",
  "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": "Fully Remote"}},
  "applicantLocationRequirements": [{"@type": "Country", "name": "Rwanda"}, {"@type": "Country", "name": "Kenya"}],
  "hiringOrganization": {"@type": "Organization", "name": "Kigali AI Lab"},
  "description": "<p>Remote AI engineering role open to Rwandan applicants.</p>"
}
</script>
"""


def transport_for(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_remoteok_parses_worldwide_and_skips_metadata():
    def handler(request):
        return httpx.Response(200, json=REMOTE_OK_PAYLOAD)

    board = RemoteOKBoard(transport=transport_for(handler))
    jobs = await board.fetch(limit=10)
    assert len(jobs) == 2
    assert jobs[0].title == "Python Engineer"
    assert jobs[0].company == "Acme Remote"
    assert jobs[0].location == "🌏"
    assert "python" in jobs[0].tags


@pytest.mark.asyncio
async def test_weworkremotely_parses_region():
    def handler(request):
        return httpx.Response(200, text=WWR_HTML, headers={"content-type": "text/html"})

    board = WeWorkRemotelyBoard(transport=transport_for(handler))
    jobs = await board.fetch(limit=10)
    assert len(jobs) == 2
    assert jobs[0].title == "Django Developer"
    assert jobs[0].location == "Anywhere in the World"
    assert jobs[1].location == "USA only"


@pytest.mark.asyncio
async def test_remote4africa_extracts_country_list():
    def handler(request):
        if "/jobs/" in request.url.path:
            if "rwanda" in request.url.path:
                return httpx.Response(200, text=R4A_DETAIL_HTML, headers={"content-type": "text/html"})
            return httpx.Response(200, text="<html><h1>No structured data</h1></html>",
                                  headers={"content-type": "text/html"})
        return httpx.Response(200, text=R4A_LISTING_HTML, headers={"content-type": "text/html"})

    board = Remote4AfricaBoard(transport=transport_for(handler))
    jobs = await board.fetch(limit=5)
    assert len(jobs) == 1
    assert jobs[0].title == "Python AI Engineer"
    assert jobs[0].company == "Kigali AI Lab"
    assert jobs[0].eligible_countries == ["Rwanda", "Kenya"]
    assert jobs[0].remote == "Remote"


@pytest.mark.asyncio
async def test_remote4africa_skips_non_jsonld_pages():
    def handler(request):
        if "/jobs/" in request.url.path:
            return httpx.Response(200, text="<html><h1>No structured data</h1></html>",
                                  headers={"content-type": "text/html"})
        return httpx.Response(200, text=R4A_LISTING_HTML, headers={"content-type": "text/html"})

    board = Remote4AfricaBoard(transport=transport_for(handler))
    jobs = await board.fetch(limit=5)
    assert jobs == []


# ── Himalayas ────────────────────────────────────────────────────────────

HIMALAYAS_WORLDWIDE_PAYLOAD = {
    "totalCount": 2,
    "offset": 0,
    "limit": 20,
    "jobs": [
        {
            "title": "Senior Python Engineer",
            "companyName": "Acme Corp",
            "applicationLink": "https://himalayas.app/jobs/senior-python-engineer",
            "locationRestrictions": [],
            "minSalary": 80000,
            "maxSalary": 120000,
            "currency": "USD",
            "categories": ["Engineering", "Python"],
            "excerpt": "Build backend systems.",
            "pubDate": "2026-08-17T00:00:00Z",
        },
        {
            "title": "UK Only Role",
            "companyName": "Brit Co",
            "applicationLink": "https://himalayas.app/jobs/uk-role",
            "locationRestrictions": ["GB"],
            "minSalary": None,
            "maxSalary": None,
            "currency": "GBP",
            "categories": ["Design"],
            "excerpt": "Design role.",
            "pubDate": "2026-08-16T00:00:00Z",
        },
    ],
}


@pytest.mark.asyncio
async def test_himalayas_parses_worldwide_and_country_restricted():
    def handler(request):
        return httpx.Response(200, json=HIMALAYAS_WORLDWIDE_PAYLOAD)

    board = HimalayasBoard(transport=transport_for(handler))
    jobs = await board.fetch(limit=10)
    assert len(jobs) == 2
    assert jobs[0].title == "Senior Python Engineer"
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].location == "Worldwide"
    assert jobs[0].remote == "Remote"
    assert jobs[1].location == "GB"
    assert jobs[1].remote == ""  # country-restricted, not marked remote


# ── Remotive ───────────────────────────────────────────────────────────

REMOTIVE_PAYLOAD = {
    "job-count": 3,
    "jobs": [
        {
            "id": 101,
            "title": "React Developer",
            "company_name": "StartupX",
            "url": "https://remotive.com/remote-jobs/react-developer-101",
            "candidate_required_location": "Worldwide",
            "category": "Software Development",
            "salary": "$80k - $120k",
            "description": "<p>Build React apps.</p>",
            "publication_date": "2026-08-17T00:00:00",
        },
        {
            "id": 102,
            "title": "US Only Designer",
            "company_name": "US Corp",
            "url": "https://remotive.com/remote-jobs/designer-102",
            "candidate_required_location": "United States",
            "category": "Design",
            "salary": "",
            "description": "Design role.",
            "publication_date": "2026-08-16T00:00:00",
        },
        {
            "id": 103,
            "title": "Backend Engineer",
            "company_name": "CloudCo",
            "url": "https://remotive.com/remote-jobs/backend-103",
            "candidate_required_location": "",
            "category": "Software Development",
            "salary": "$100k",
            "description": "Python backend.",
            "publication_date": "2026-08-15T00:00:00",
        },
    ],
}


@pytest.mark.asyncio
async def test_remotive_parses_worldwide_and_country_restricted():
    def handler(request):
        return httpx.Response(200, json=REMOTIVE_PAYLOAD)

    board = RemotiveBoard(transport=transport_for(handler))
    jobs = await board.fetch(limit=10)
    assert len(jobs) == 3
    assert jobs[0].title == "React Developer"
    assert jobs[0].company == "StartupX"
    assert jobs[0].location == "Worldwide"
    assert jobs[0].remote == "Remote"
    assert jobs[0].board == "remotive"
    assert jobs[1].location == "United States"
    assert jobs[1].remote == ""  # country-restricted
    assert jobs[2].location == ""  # empty = worldwide
