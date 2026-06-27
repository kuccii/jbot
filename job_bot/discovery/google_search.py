import httpx
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import is_rwanda_tanzania_eligible

# ── Known aggregator / non-direct listing domains to exclude ──────────────
AGGREGATOR_DOMAINS = [
    "remotive.com", "remoteok.com", "weworkremotely.com",
    "remotejobsafrica.com", "remotecareer.africa", "remoteli.com",
    "upwork.com", "toptal.com", "freelancer.com", "fiverr.com",
    "workana.com", "peopleperhour.com", "progigfinder.com",
    "indeed.com", "ziprecruiter.com", "monster.com", "simplyhired.com",
    "glassdoor.com", "careerbuilder.com", "flexjobs.com",
    "dynamitejobs.com", "remoterocketship.com", "remote4africa.com",
    "crossover.com", "seganrecruitment.com", "careerhound.io", "fuzu.com",
    "globalhire360.com", "jobgether.com",
    "tunga.io", "gebeya.com",
    "arc.dev", "mctaba.com",
    "youtube.com", "youtu.be",
    "wellfound.com",
    "himalayas.app", "rubyonremote.com",
    "reddit.com", "remote.co", "nodesk.co",
    "remoteafrica.io", "substack.com",
    "jobviewtrack.com",
    "linkedin.com",
]

# ── Job queries — direct company listings + specific boards ───────────────
JOB_QUERIES = [
    "global remote developer jobs open to africa 2026",
    "international remote jobs hiring worldwide africa",
    "remote software engineer africa timezone 2026",
    "site:wellfound.com startup jobs remote worldwide",
    "remote full stack developer contract worldwide",
    "remote AI engineer contract global 2026",
    "hiring remote developers africa remote job",
    "site:linkedin.com remote jobs worldwide entry level",
    "remote jobs for african developers 2026",
]

# ── Startup queries — strictly Rwanda/Tanzania / East Africa ──────────────
STARTUP_QUERIES = [
    "develoPPP Ventures funding Rwanda Tanzania 2026",
    "GIZ develoPPP startup funding Rwanda Tanzania East Africa",
    "site:developpp.de ventures call Rwanda Tanzania",
    "east africa startup funding program 2026",
    "Rwanda startup incubator accelerator 2026",
    "Tanzania digital entrepreneurship program 2026",
    "German development cooperation Rwanda Tanzania startup",
    "invest-for-jobs develoPPP call proposals Rwanda Tanzania",
    "KfW development bank Rwanda Tanzania startup",
    "Rwanda tech startup government support 2026",
]

# ── Grant queries — strictly Rwanda/Tanzania / East Africa ────────────────
GRANT_QUERIES = [
    "Rwanda Tanzania grant funding 2026",
    "fellowship Rwanda Tanzania 2026",
    "east africa grant funding opportunities 2026",
    "site:opportunitydesk.org Rwanda Tanzania grant 2026",
    "site:opportunitiesforafricans.com Rwanda Tanzania grant",
    "GIZ bilateral cooperation grant Rwanda Tanzania 2026",
    "UNDP innovation challenge Rwanda Tanzania 2026",
    "World Bank youth program Rwanda Tanzania",
    "African Development Bank grant Rwanda Tanzania",
    "USaid Rwanda Tanzania grant program 2026",
    "EU Horizon Europe Africa grant Rwanda Tanzania",
]


@register("google_search")
class GoogleSearchScraper(BaseScraper):
    def __init__(self):
        self.api_key = ""

    def set_api_key(self, key: str):
        self.api_key = key

    async def _search(self, q: str) -> list[dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": q, "num": 10},
                    headers={"X-API-KEY": self.api_key},
                )
                return resp.json().get("organic", [])
        except Exception:
            return []

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self.api_key:
            return []
        results = []
        seen = set()

        # Build query lists
        job_qs = list(JOB_QUERIES)
        startup_qs = list(STARTUP_QUERIES)
        grant_qs = list(GRANT_QUERIES)

        # Skills → job queries
        for skill in criteria.skills:
            job_qs.append(f"{skill} 1099 contract remote 2026")
            job_qs.append(f"hire {skill} freelance remote")

        # Keywords → startup + grant queries (Rwanda/Tanzania scoped)
        for kw in criteria.keywords:
            startup_qs.append(f"{kw} Rwanda Tanzania startup 2026")
            grant_qs.append(f"{kw} Rwanda Tanzania grant 2026")

        for q, category, geography_check in [
            *[(q, "job", False) for q in job_qs],
            *[(q, "startup", True) for q in startup_qs],
            *[(q, "grant", True) for q in grant_qs],
        ]:
            items = await self._search(q)
            for item in items:
                link = item.get("link", "")
                if link in seen:
                    continue
                seen.add(link)
                snippet = item.get("snippet", "")
                title = item.get("title", "")
                # Skip known aggregator / non-direct listing domains
                link_lower = link.lower()
                if any(d in link_lower for d in AGGREGATOR_DOMAINS):
                    continue
                if geography_check and not is_rwanda_tanzania_eligible(title, snippet):
                    continue
                results.append(Opportunity(
                    title=title,
                    company=item.get("source", ""),
                    url=link,
                    description=snippet,
                    source="google_search",
                    category=category,
                ))
        return results
