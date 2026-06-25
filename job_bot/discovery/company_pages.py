import re
import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("company_pages")
class CompanyPagesScraper(BaseScraper):
    def __init__(self):
        self.entries: list[str] = []

    def set_companies(self, entries: list[str]):
        self.entries = entries

    def _resolve_url(self, entry: str) -> str:
        entry = entry.strip()
        if entry.startswith(("http://", "https://")):
            return entry
        return f"https://{entry}.com/careers"

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        job_keywords = re.compile(
            r"(career|job|position|opening|vacanc|opportunit|apply|hiring|work\s*with\s*us|join\s*our\s*team)",
            re.IGNORECASE,
        )
        opportunities = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for entry in self.entries:
                url = self._resolve_url(entry)
                try:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    title_tag = soup.find("title")
                    page_title = title_tag.text.strip() if title_tag else entry
                    links_found = 0
                    for a_tag in soup.find_all("a", href=True):
                        text = a_tag.get_text(strip=True)
                        href = a_tag["href"]
                        if len(text) < 5 or not job_keywords.search(text) and not job_keywords.search(href):
                            continue
                        full_url = href if href.startswith("http") else resp.url.join(href).href
                        opportunities.append(Opportunity(
                            title=text[:200],
                            company=entry,
                            url=full_url,
                            description=page_title,
                            source="company_pages",
                            category="job",
                        ))
                        links_found += 1
                    if not links_found:
                        opportunities.append(Opportunity(
                            title=f"Careers at {entry}",
                            company=entry,
                            url=url,
                            description=page_title,
                            source="company_pages",
                            category="job",
                        ))
                except Exception:
                    pass
        return opportunities
