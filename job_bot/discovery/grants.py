from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("grants")
class GrantScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        sources = [
            ("https://www.grants.gov/web/grants/search-grants.html", "grants.gov"),
        ]
        for url, source in sources:
            opportunities.append(Opportunity(
                title=f"Check {source} for latest grants",
                company=source,
                url=url,
                source=source,
                description=f"Visit {url} for current grant opportunities matching your skills.",
            ))
        return opportunities
