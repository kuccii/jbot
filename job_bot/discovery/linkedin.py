import httpx
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import is_rwanda_tanzania_eligible

# ── Job queries — broad LinkedIn job searches ─────────────────────────────
JOB_QUERIES = [
    "site:linkedin.com freelance remote developer 2026",
    "site:linkedin.com jobs contract developer remote",
    "site:linkedin.com remote AI engineer",
    "site:linkedin.com remote product designer",
    "site:linkedin.com freelance software engineer",
]

# ── Startup queries — strictly Rwanda/Tanzania / East Africa ──────────────
STARTUP_QUERIES = [
    "site:linkedin.com developpp Rwanda Tanzania",
    "site:linkedin.com startup funding East Africa",
    "site:linkedin.com Rwanda tech startup incubator",
    "site:linkedin.com Tanzania startup accelerator",
]

# ── Grant queries — strictly Rwanda/Tanzania / East Africa ────────────────
GRANT_QUERIES = [
    "site:linkedin.com grant Rwanda Tanzania 2026",
    "site:linkedin.com fellowship East Africa",
    "site:linkedin.com Rwanda scholarship program",
]


@register("linkedin")
class LinkedInScraper(BaseScraper):
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

        job_qs = list(JOB_QUERIES)
        startup_qs = list(STARTUP_QUERIES)
        grant_qs = list(GRANT_QUERIES)

        for skill in criteria.skills:
            job_qs.append(f"site:linkedin.com {skill} freelance remote 2026")
            job_qs.append(f"site:linkedin.com jobs {skill} contract")

        for kw in criteria.keywords:
            startup_qs.append(f"site:linkedin.com {kw} Rwanda Tanzania")
            grant_qs.append(f"site:linkedin.com {kw} grant Rwanda Tanzania")

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
                if geography_check and not is_rwanda_tanzania_eligible(title, snippet):
                    continue
                results.append(Opportunity(
                    title=title,
                    company=item.get("source", "LinkedIn"),
                    url=link,
                    description=snippet,
                    source="linkedin",
                    category=category,
                ))
        return results
