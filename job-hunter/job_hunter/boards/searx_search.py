"""SearXNG-powered job search boards.

Instead of scraping job sites directly (many block bots with Cloudflare,
WAF, or bot-detection), we query a self-hosted SearXNG instance. SearXNG
aggregates Google/Bing/other engines, so it returns live listings that
a direct request would never get:

  - Indeed real ``viewjob`` links (their site 401s direct bot requests,
    but search engines index the public job pages)
  - Visa-sponsorship postings across many ATS/job sites

The SearXNG instance runs on the VPS (http://72.60.188.94:50361) and the
JSON format is enabled in its settings.yml.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from html import unescape

import httpx

from job_hunter.boards.base import Board
from job_hunter.fetch import DEFAULT_HEADERS
from job_hunter.eligibility import VISA_POSITIVE, VISA_NEGATIVE
from job_hunter.models import Job

# Default SearXNG instance (VPS). Override with SEARXNG_URL env var or
# config.yaml's ``websearch.url``.
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://72.60.188.94:50361")
SEARXNG_TIMEOUT = 40.0
SEARXNG_MAX_PAGES = 1  # one page per query (each ~ 20-40 results)

# SearXNG lives on the VPS (datacenter IP). Search engines CAPTCHA/suspend
# datacenter IPs after a burst of rapid queries, so we pace requests:
# low concurrency + a small delay between pages/queries.
SEARXNG_CONCURRENCY = 2
SEARXNG_PAGE_DELAY = 1.0   # seconds between pages of one query
SEARXNG_QUERY_DELAY = 1.5  # seconds between queries in a board


def _searxng_url() -> str:
    """Return the configured SearXNG base URL.

    Precedence: SEARXNG_URL env var > config.yaml websearch.url > default.
    """
    env = os.getenv("SEARXNG_URL")
    if env:
        return env.rstrip("/")
    try:
        from job_hunter.config import load_config
        url = load_config().websearch.url
        if url:
            return url.rstrip("/")
    except Exception:
        pass
    return SEARXNG_URL.rstrip("/")


async def searxng_search(
    client: httpx.AsyncClient,
    query: str,
    language: str = "en",
    pages: int = SEARXNG_MAX_PAGES,
) -> list[dict]:
    """Run a query against the SearXNG JSON API.

    Returns raw result dicts (title/url/content/engine/...).
    """
    results: list[dict] = []
    for page in range(1, pages + 1):
        params = {
            "q": query,
            "format": "json",
            "language": language,
            "pageno": page,
            "safesearch": "0",
            "categories": "general",
        }
        try:
            resp = await client.get(
                f"{_searxng_url()}/search", params=params, timeout=SEARXNG_TIMEOUT
            )
            if resp.status_code != 200:
                await asyncio.sleep(1.0)
                continue
            data = resp.json()
            results.extend(data.get("results", []))
        except Exception:
            # Individual page failures shouldn't kill the whole board
            break
        if page > 1 and not results:
            break
        await asyncio.sleep(SEARXNG_PAGE_DELAY)
    return results


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _clean_title(text: str) -> str:
    """Strip site suffixes like ' - Indeed' or ' | RemoteOK'."""
    title = _clean(text)
    # Common suffixes: " - Indeed", " | Indeed", " | Indeed.com", " - Indeed.com"
    title = re.sub(
        r"\s*[-–—|]\s*(Indeed(\.com)?|RemoteOK|Working Nomads|Jobicy|remotive|FlexJobs)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )
    return title.strip()


class SearxSearchBoard(Board):
    """Base class: run a list of search queries and turn results into jobs.

    Subclasses define ``QUERIES`` (list of search query strings) and a
    ``_result_to_job(result) -> Job | None`` parser.
    """

    name: str = ""
    label: str = ""
    QUERIES: list[str] = []

    # Site/engine spam that shows up in job searches but isn't a job board.
    JUNK_DOMAINS = {
        "migratemate.co", "applywave.app", "jaabz.com", "globalsponsorhub.com",
        "workvisa.com", "immigrationdirect.com", "visasolution.com",
        "usavisa.com", "germany-visa.org", "ukimmigration.com",
    }

    async def fetch(self, limit: int = 500) -> list[Job]:
        jobs: list[Job] = []
        seen_urls: set[str] = set()
        sem = asyncio.Semaphore(SEARXNG_CONCURRENCY)

        async def _run_query(client: httpx.AsyncClient, query: str) -> None:
            if len(jobs) >= limit:
                return
            async with sem:
                try:
                    results = await searxng_search(client, query)
                except Exception:
                    return
                await asyncio.sleep(SEARXNG_QUERY_DELAY)
            for result in results:
                if len(jobs) >= limit:
                    return
                job = self._result_to_job(result)
                if job is None:
                    continue
                # De-dupe on normalized URL
                norm_url = job.url.split("?")[0].rstrip("/")
                if norm_url in seen_urls:
                    continue
                seen_urls.add(norm_url)
                jobs.append(job)

        async with self.client() as client:
            await asyncio.gather(*(_run_query(client, q) for q in self.QUERIES))

        return jobs

    def _result_to_job(self, result: dict) -> Job | None:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════
# Indeed via search
# ═══════════════════════════════════════════════════════════════════════

INDEED_DOMAIN_RE = re.compile(
    r"https?://(?:[a-z0-9-]+\.)*indeed\.(?:com|co\.uk|de|fr|nl|ie|es|it|pl|se|ch|at|pt|no|dk|fi|be|ca|com\.au|sg|co\.in|co\.za)/viewjob\?jk=[0-9A-Za-z]+",
    re.IGNORECASE,
)

# Role phrases -> audience tag for the resulting jobs.
INDEED_ROLE_QUERIES: list[str] = [
    'site:indeed.com/viewjob "remote data entry"',
    'site:indeed.com/viewjob "remote virtual assistant"',
    'site:indeed.com/viewjob "remote customer support"',
    'site:indeed.com/viewjob "remote admin assistant"',
    'site:indeed.com/viewjob "remote transcription"',
    'site:indeed.com/viewjob "remote bookkeeper"',
    'site:indeed.com/viewjob "remote IT support"',
    'site:indeed.com/viewjob "remote chat support"',
    'site:indeed.com/viewjob "remote call center"',
    # European Indeed country domains (user request: target European Indeed)
    'site:www.indeed.co.uk "remote" "data entry" OR "customer support"',
    'site:www.indeed.de "remote" "data entry" OR "customer support"',
    'site:www.indeed.fr "remote" "data entry" OR "customer support"',
    'site:www.indeed.ie "remote" "customer support" OR "virtual assistant"',
    'site:www.indeed.nl "remote" "data entry" OR "customer support"',
]

# Phrases that indicate the role is truly remote + location-flexible.
REMOTE_FLEX_SIGNALS = re.compile(
    r"\b(remote|work from home|work-from-home|home based|online|virtual)\b",
    re.IGNORECASE,
)
# Phrases that indicate the posting is locked to a specific country/work auth.
RESTRICTION_SIGNALS = re.compile(
    r"\b(us citizenship|must be authorized to work in the us|authorized to work in "
    r"the united states|must be based in|based in the us|us only|uk only|eu only|"
    r"must live in|eligible to work in|right to work in|work authorization required|"
    r"no visa sponsorship|no sponsorship|cannot sponsor|will not sponsor|do not sponsor|"
    r"does not sponsor)\b",
    re.IGNORECASE,
)
# Phrases that indicate wide-open remote (anywhere/worldwide).
WORLDWIDE_SIGNALS = re.compile(
    r"\b(anywhere|worldwide|global|any country|european time zones?|work from anywhere)\b",
    re.IGNORECASE,
)
# Country/city anchors that mean a "remote" posting is really remote within
# one country (e.g. "Remote Data Entry - Manila", "Remote VA - Lagos").
# Those aren't open to someone in Rwanda, so drop unless a worldwide signal
# is present.
LOCAL_ANCHORS = re.compile(
    r"\b(manila|lagos|nairobi|accra|cairo|alberta|ontario|toronto|quebec|british "
    r"columbia|egypt|nigeria|kenya|ghana|philippines|india|bangalore|bengaluru|"
    r"mumbai|delhi|dubai|abu dhabi|riyadh|qatar|singapore|kuala lumpur|jakarta|"
    r"mexico|colombia|bogota|sao paulo|brazil|argentina|chile|peru|lima|santiago|"
    r"australia|sydney|melbourne|new zealand|canada|usa|u\.?s\.?a|united states|"
    r"united kingdom|uk|england|ireland|poland|germany|france|netherlands|holland|"
    r"belgium|switzerland|austria|italy|spain|portugal|denmark|sweden|norway|"
    r"finland|ukraine|poland|czech|hungary|romania|\u0645\u0635\u0631)\b",
    re.IGNORECASE,
)


class IndeedSearchBoard(SearxSearchBoard):
    """Find real Indeed ``viewjob`` links via SearXNG web search.

    Indeed blocks direct scraping (401 bot detection), but search engines
    index their public job pages. Each result keeps the canonical
    ``https://<country>.indeed.com/viewjob?jk=...`` URL, which opens in a
    normal browser. Titles/snippets are the search-engine text, not a
    full scrape, so eligibility relies on remote signals in what we have.
    """

    name = "indeed_search"
    label = "Indeed via Web Search (real viewjob links)"

    QUERIES = INDEED_ROLE_QUERIES

    async def fetch(self, limit: int = 500) -> list[Job]:
        return await super().fetch(limit=limit)

    def _result_to_job(self, result: dict) -> Job | None:
        url = _clean(result.get("url"))
        if not INDEED_DOMAIN_RE.search(url):
            return None

        title = _clean_title(result.get("title"))
        content = _clean(result.get("content"))

        if not title or len(title) < 8:
            return None

        # Skip titles that are clearly not a job posting
        low = f"{title} {content}".lower()
        if any(s in low for s in ["sign in", "create account", "indeed login", "find jobs"]):
            return None

        # Title must itself lead with a remote-first signal ("Remote X",
        # "Work From Home X", "Virtual X"). Merely mentioning remote in a
        # snippet isn't enough — we can't verify a non-leading role is open
        # to Rwanda without fetching the page (which Indeed blocks).
        if not re.match(
            r"^(remote|work from home|work-from-home|virtual|online|home based)[, \-–—]?\s",
            title,
            re.IGNORECASE,
        ):
            return None

        # Drop postings anchored to a physical city/province inside the title
        # (e.g. "Remote Data Entry Clerk - La Ronge, SK") — those are remote
        # within one country/region, not open worldwide.
        if re.search(r",\s*[A-Z]{2}\s*$", title):
            return None
        # Country/city anchor in the title means local-only remote, unless a
        # worldwide signal is present in title+snippet.
        if LOCAL_ANCHORS.search(title) and not WORLDWIDE_SIGNALS.search(low):
            return None

        # Work-authorization / country restrictions that exclude non-US etc.
        if RESTRICTION_SIGNALS.search(low) and not WORLDWIDE_SIGNALS.search(low):
            return None

        # Keep only postings that read as remote-flexible. If the snippet
        # shows nothing remote and the title has none, we can't verify the
        # role is remote -> drop (we never claim eligibility for unknown).
        if not REMOTE_FLEX_SIGNALS.search(low):
            return None

        # Search-result titles are "<Job Title> - <Site>" only; the employer
        # name isn't reliably present, so leave company empty rather than
        # guessing wrong (e.g. grabbing "Manila" as the company).

        location = "Remote Worldwide" if WORLDWIDE_SIGNALS.search(low) else "Remote"

        # Country tag from the URL domain (www.indeed.com -> US etc.)
        m = re.search(r"indeed\.([a-z.]+)", url)
        country = m.group(1) if m else "com"

        return Job(
            title=title,
            company="",
            url=url,
            board=self.name,
            location=location,
            remote="Remote",
            tags=f"indeed {country}",
            description=f"Indeed ({country}) — found via web search.\n{content}",
            posted_at="",
            eligible_countries=[],
            audience="entry",
        )


# ═══════════════════════════════════════════════════════════════════════
# Visa sponsorship via search
# ═══════════════════════════════════════════════════════════════════════

VISA_QUERIES: list[str] = [
    'site:boards.greenhouse.io "visa sponsorship" OR "relocation support"',
    'site:job-boards.greenhouse.io "visa sponsorship"',
    'site:jobs.ashbyhq.com "visa sponsorship" OR "sponsorship"',
    'site:jobs.lever.co "visa sponsorship" OR "relocation"',
    'site:jobs.smartrecruiters.com "visa sponsorship" OR "relocation support"',
    '"visa sponsorship" remote customer service job',
    '"visa sponsorship" remote data entry job',
    '"visa sponsorship" remote virtual assistant',
    '"visa sponsorship" english speaking remote europe',
    '"we sponsor visas" OR "we will sponsor" remote job',
    '"sponsorship available" "remote" data entry OR customer support',
    '"relocation support" OR "relocation package" remote entry level',
    'site:startup.jobs "visa sponsorship"',
    '"work permit sponsorship" remote entry level',
]

# Only keep result pages that look like actual job postings on a real
# employer ATS / job board — not visa-agency landing pages.
VISA_JOB_URL_RE = re.compile(
    r"https?://(?:"
    r"[a-z0-9-]*\.?(?:greenhouse\.io|ashbyhq\.com|lever\.co|smartrecruiters\.com"
    r"|workable\.com|bamboohr\.com|jobvite\.com|workday\.com|recruitee\.com"
    r"|teamtailor\.com|personio\.com|join\.com|startup\.jobs|remoteok\.com|remotive\.com)"
    r"|(?:[a-z0-9-]+\.)*indeed\.(?:com|co\.uk|de|fr|nl|ie|es|it|pl|se|ch|at|pt|no|dk|fi|be|ca|com\.au|sg|co\.in|co\.za)/viewjob\?jk=[0-9A-Za-z]+"
    r")",
    re.IGNORECASE,
)

class VisaSponsorshipBoard(SearxSearchBoard):
    """Find employer postings that explicitly offer visa sponsorship or
    relocation — via SearXNG web search.

    These are jobs that sponsor a work visa/relocation for candidates
    abroad. Eligibility is a *visa-sponsorship* check (the employer moves
    you), which the orchestrator handles by calling the visa helper in
    ``eligibility.py`` instead of the location-based Rwanda check.
    """

    name = "visa_sponsorship"
    label = "Visa Sponsorship / Relocation (via Web Search)"

    QUERIES = VISA_QUERIES

    def _result_to_job(self, result: dict) -> Job | None:
        url = _clean(result.get("url"))
        if not VISA_JOB_URL_RE.search(url):
            return None
        host = re.sub(r"^https?://", "", url).split("/")[0]

        title = _clean_title(result.get("title"))
        content = _clean(result.get("content"))
        if not title or len(title) < 8:
            return None

        low = f"{title} {content}".lower()
        # Explicit negative beats everything
        if VISA_NEGATIVE.search(low):
            return None
        if not VISA_POSITIVE.search(low):
            return None

        # Company: extract from ATS host slug where obvious
        company = ""
        m = re.search(r"greenhouse\.io/([^/]+)", url)
        if m:
            company = m.group(1).replace("-", " ").title()
        if not company:
            m = re.search(r"ashbyhq\.com/([^/]+)", url)
            if m:
                company = m.group(1).replace("-", " ").title()
        if not company:
            m = re.search(r"lever\.co/([^/]+)", url)
            if m:
                company = m.group(1).replace("-", " ").title()

        return Job(
            title=title,
            company=company,
            url=url,
            board=self.name,
            location="",          # checked by the visa helper, not location
            remote="",
            tags="visa-sponsorship relocation",
            description=f"Employer offers visa sponsorship / relocation support.\n{content}",
            posted_at="",
            eligible_countries=[],
            audience="visa",
        )
