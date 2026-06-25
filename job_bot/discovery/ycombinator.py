import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("ycombinator")
class YCombinatorScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        urls = [
            "https://www.workatastartup.com/companies",
            "https://www.ycombinator.com/jobs",
        ]
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for url in urls:
                try:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    titles_seen = set()
                    for a_tag in soup.find_all("a", href=True):
                        text = a_tag.get_text(strip=True)
                        href = a_tag["href"]
                        if len(text) < 5:
                            continue
                        full_url = href if href.startswith("http") else f"https://www.ycombinator.com{href}"
                        key = f"{text}|{full_url}"
                        if key in titles_seen:
                            continue
                        titles_seen.add(key)
                        opportunities.append(Opportunity(
                            title=text[:200],
                            company="Y Combinator Startup",
                            url=full_url,
                            description=f"YC startup opportunity: {text}",
                            source="ycombinator",
                            category="startup",
                        ))
                except Exception:
                    pass
        return opportunities
