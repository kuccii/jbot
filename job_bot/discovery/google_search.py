import httpx
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("google_search")
class GoogleSearchScraper(BaseScraper):
    def __init__(self):
        self.api_key = ""

    def set_api_key(self, key: str):
        self.api_key = key

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self.api_key:
            return []
        async with httpx.AsyncClient() as client:
            results = []
            seen = set()
            queries = []
            for skill in criteria.skills:
                queries.append(f"{skill} 1099 contract remote 2026")
                queries.append(f"hire {skill} freelance remote")
            for kw in criteria.keywords:
                queries.append(f"{kw} grant funding 2026")
            queries.append("remote contract developer Africa 2026")
            queries.append("remote AI engineer contract 2026")
            queries.append("develoPPP Ventures funding Rwanda Tanzania 2026")
            queries.append("develoPPP GIZ startup funding East Africa")
            queries.append("GIZ develoPPP jobs Rwanda Kenya Tanzania")
            queries.append("invest-for-jobs develoPPP call proposals")
            queries.append("startup funding grant Rwanda East Africa 2026")
            queries.append("German development cooperation tech Africa apply")
            queries.append("Rwanda tech startup incubator accelerator 2026")
            queries.append("Tanzania digital jobs freelance platform")
            queries.append("german development cooperation startup program africa 2026")
            queries.append("eu horizon europe africa innovation grants 2026")
            queries.append("world bank africa youth entrepreneurship program 2026")
            queries.append("undp africa innovation challenge 2026")
            queries.append("african development bank youth jobs program 2026")
            queries.append("japan international cooperation agency africa startup 2026")
            queries.append("french development agency afd africa entrepreneurship 2026")
            queries.append("usaid africa tech ecosystem support program 2026")
            queries.append("east africa grant funding opportunities portal 2026")
            queries.append("rwanda startup government support program 2026")
            queries.append("tanzania digital entrepreneurship grant 2026")
            queries.append("kenya tech innovation hub accelerator 2026")
            queries.append("giz bilateral cooperation tender rwanda 2026")
            queries.append("kfw development bank africa startup 2026")
            queries.append("site:developpp.de ventures call 2026")
            queries.append("site:giz.de jobs rwanda tanzania 2026")
            queries.append("site:opportunitydesk.org rwanda 2026")
            queries.append("site:opportunitiesforafricans.com grant 2026")
            for q in queries:
                try:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        json={"q": q, "num": 10},
                        headers={"X-API-KEY": self.api_key},
                    )
                    data = resp.json()
                    for item in data.get("organic", []):
                        link = item.get("link", "")
                        if link not in seen:
                            seen.add(link)
                            results.append(Opportunity(
                                title=item.get("title", ""),
                                company=item.get("source", ""),
                                url=link,
                                description=item.get("snippet", ""),
                                source="google_search",
                                category="job",
                            ))
                except Exception:
                    pass
            return results
