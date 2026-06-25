from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("company_pages")
class CompanyPagesScraper(BaseScraper):
    def __init__(self):
        self.companies: list[str] = []

    def set_companies(self, companies: list[str]):
        self.companies = companies

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        for company in self.companies:
            opportunities.append(Opportunity(
                title=f"Careers at {company}",
                company=company,
                url=f"https://{company}.com/careers",
                source="company_pages",
                description=f"Career page for {company}. Check for open positions.",
                category="job",
            ))
        return opportunities
