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
SEARXNG_QUERY_DELAY = 2.5  # seconds between queries in a board


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

    def _extra_queries(self) -> list[str]:
        """Board-specific queries appended from config (websearch.extra_queries).

        Lets users extend searches without touching code:

            websearch:
              extra_queries:
                indeed_search: ["site:indeed.com/viewjob \"remote data entry\" \"entry level\""]
        """
        extra: list[str] = []
        try:
            from job_hunter.config import load_config
            extra = (load_config().websearch.extra_queries or {}).get(self.name, [])
        except Exception:
            pass
        return [q for q in extra if isinstance(q, str) and q.strip()]

    def _queries(self) -> list[str]:
        """All queries for this board: built-ins + config extras, de-duped."""
        queries = list(self.QUERIES) + self._extra_queries()
        seen: set[str] = set()
        unique = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)
        return unique

    def _queries_per_run(self) -> int:
        """Max queries to run in a single fetch.

        SearXNG sits on a datacenter IP: search engines suspend it after a
        burst (~10-25 rapid queries). We keep a large pool of queries but
        sample a rotating subset each run, so a discovery adds fresh jobs
        without tripping rate limits, and later runs cover the rest.

        Tunable via config: websearch.queries_per_run (default 12).
        """
        try:
            from job_hunter.config import load_config
            n = load_config().websearch.queries_per_run
            if n and n > 0:
                return int(n)
        except Exception:
            pass
        return 12

    def _active_queries(self) -> list[str]:
        """Random rotating subset of queries for this run.

        A discovery run picks a different random sample each time, so the
        full pool gets covered across runs while each run stays under the
        datacenter-IP burst limit.
        """
        import random
        all_q = self._queries()
        n = self._queries_per_run()
        if len(all_q) <= n:
            return all_q
        return random.sample(all_q, min(n, len(all_q)))

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
            await asyncio.gather(*(_run_query(client, q) for q in self._active_queries()))

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

# Entry-level / fast-start roles that a Rwandan can realistically do
# remotely. Each gets a site-scoped query against the Indeed index.
INDEED_ROLE_PHRASES: list[str] = [
    "data entry",
    "virtual assistant",
    "customer support",
    "customer service",
    "admin assistant",
    "administrative assistant",
    "transcription",
    "transcriber",
    "bookkeeper",
    "IT support",
    "technical support",
    "help desk",
    "chat support",
    "call center",
    "data analyst",
    "proofreader",
    "copywriter",
    "content writer",
    "social media",
    "search engine evaluator",
    "online tutor",
    "english teacher",
    "medical billing",
    "medical coding",
    "scheduler",
    "dispatcher",
    "recruiter",
    "sales representative",
    "appointment setter",
    "web researcher",
    "data annotation",
]

# All working Indeed country TLDs + their subdomain (from indeed.py).
INDEED_DOMAINS: list[str] = [
    # Europe
    "www.indeed.co.uk", "www.indeed.de", "www.indeed.nl", "www.indeed.ie",
    "www.indeed.fr", "www.indeed.be", "www.indeed.cz", "www.indeed.hu",
    "www.indeed.no", "www.indeed.fi", "www.indeed.pt", "www.indeed.es",
    "www.indeed.ch", "www.indeed.it", "www.indeed.se", "www.indeed.pl",
    "www.indeed.at", "www.indeed.dk", "www.indeed.lu",
    # Americas + APAC + Africa
    "www.indeed.com", "www.indeed.ca", "www.indeed.com.au", "www.indeed.sg",
    "www.indeed.co.in", "www.indeed.co.za",
]

# Queries: main site for every role + country sites for the top roles.
# Kept bounded so a full run stays under ~60 SearXNG requests.
INDEED_ROLE_QUERIES: list[str] = []
for _phrase in INDEED_ROLE_PHRASES:
    INDEED_ROLE_QUERIES.append(f'site:indeed.com/viewjob "remote {_phrase}"')
for _dom in ["www.indeed.co.uk", "www.indeed.de", "www.indeed.ie", "www.indeed.nl"]:
    INDEED_ROLE_QUERIES.append(f'site:{_dom}/viewjob "remote" "data entry" OR "customer support" OR "virtual assistant" OR "admin" OR "IT support"')


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
    r"finland|ukraine|poland|czech|hungary|romania|california|texas|florida|outram|\u0645\u0635\u0631)\b",
    re.IGNORECASE,
)
# Bilingual / non-English language requirements in the title that make a
# posting useless to a Rwandan (e.g. "(Chinese Speaker)", "German Speaking").
LANGUAGE_BARRIER_TITLE = re.compile(
    r"\b(chinese|mandarin|cantonese|japanese|korean|vietnamese|thai|arabic|hebrew|"
    r"turkish|russian|polish|czech|hungarian|romanian|bulgarian|dutch|swedish|"
    r"norwegian|danish|finnish|greek|ukrainian|hindi|urdu|tamil|telugu|malay|"
    r"indonesian|filipino|tagalog|german|french|italian|spanish|portuguese)\s*"
    r"(speaker|speaking|fluent|language)\b",
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
        # A non-English language requirement makes the role unusable for a
        # Rwandan without that language (e.g. "Chinese Speaker").
        if LANGUAGE_BARRIER_TITLE.search(title) and not WORLDWIDE_SIGNALS.search(low):
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
    # ── ATS host-scoped ──────────────────────────────────────────────────
    'site:boards.greenhouse.io "visa sponsorship" OR "relocation support"',
    'site:job-boards.greenhouse.io "visa sponsorship"',
    'site:boards.greenhouse.io "sponsorship available" OR "we will sponsor"',
    'site:boards.greenhouse.io "relocation package"',
    'site:jobs.ashbyhq.com "visa sponsorship" OR "sponsorship"',
    'site:jobs.lever.co "visa sponsorship" OR "relocation"',
    'site:jobs.smartrecruiters.com "visa sponsorship" OR "relocation support"',
    'site:careers.smartrecruiters.com "visa sponsorship"',
    'site:startup.jobs "visa sponsorship"',
    'site:apply.workable.com "visa sponsorship" OR "relocation"',
    'site:careers-personio.com "visa sponsorship" OR "relocation support"',
    'site:recruitee.com "visa sponsorship" OR "relocation support"',
    # ── Role-targeted (remote + sponsorship) ────────────────────────────
    '"visa sponsorship" remote customer service job',
    '"visa sponsorship" remote customer support',
    '"visa sponsorship" remote data entry job',
    '"visa sponsorship" remote virtual assistant',
    '"visa sponsorship" remote administrative assistant',
    '"visa sponsorship" remote bookkeeper',
    '"visa sponsorship" remote IT support OR help desk',
    '"visa sponsorship" remote technical support',
    '"visa sponsorship" remote sales OR account manager',
    '"visa sponsorship" remote recruiter OR HR',
    '"visa sponsorship" remote nurse OR healthcare',
    '"visa sponsorship" remote english teacher OR tutor',
    '"visa sponsorship" remote data analyst OR researcher',
    '"visa sponsorship" remote software developer OR engineer',
    # ── Wording variants ────────────────────────────────────────────────
    '"we sponsor visas" OR "we will sponsor" remote job',
    '"sponsorship available" "remote" data entry OR customer support',
    '"relocation support" OR "relocation package" remote entry level',
    '"work permit sponsorship" remote entry level',
    '"visa sponsorship available" english speaking remote',
    '"visa sponsorship" europe remote english speaking entry level',
    'site:indeed.com/viewjob "visa sponsorship" OR "relocation package"',
]

# Only keep result pages that look like actual job postings on a real
# employer ATS / job board — not visa-agency landing pages.
VISA_JOB_URL_RE = re.compile(
    r"https?://(?:"
    r"[a-z0-9-]*\.?(?:greenhouse\.io|ashbyhq\.com|lever\.co|smartrecruiters\.com"
    r"|workable\.com|bamboohr\.com|jobvite\.com|workday\.com|recruitee\.com"
    r"|teamtailor\.com|personio\.com|join\.com|startup\.jobs|remoteok\.com|remotive\.com)"
    r"|(?:[a-z0-9-]+\.)*breezy\.hr"  # Breezy HR career pages
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
