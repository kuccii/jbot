from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("linkedin")
class LinkedInScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        for skill in criteria.skills[:3]:
            opportunities.append(Opportunity(
                title=f"{skill} Contractor - LinkedIn",
                company="LinkedIn",
                url=f"https://www.linkedin.com/jobs/search/?keywords={skill}+contract",
                source="linkedin",
                description=f"LinkedIn jobs for {skill} contract positions.",
                category="job",
            ))
        return opportunities
