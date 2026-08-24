"""Dedicated scraper for Fuzu — African-focused job platform."""
import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register

FUZU_URL = "https://www.fuzu.com/jobs"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@register("fuzu")
class FuzuScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(FUZU_URL, headers={"User-Agent": USER_AGENT})
                if resp.status_code != 200:
                    return opportunities
                soup = BeautifulSoup(resp.text, "html.parser")

                for card in soup.find_all(class_=lambda c: c and "card" in (c or "").lower()):
                    title_tag = card.find("h3")
                    if not title_tag:
                        title_tag = card.find("h2")
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    if not title or len(title) < 3:
                        continue

                    link_tag = card.find("a", href=True)
                    url = ""
                    if link_tag:
                        href = link_tag["href"]
                        url = f"https://www.fuzu.com{href}" if href.startswith("/") else href

                    text = card.get_text("|", strip=True)
                    parts = [p.strip() for p in text.split("|") if p.strip()]
                    company = ""
                    location = ""
                    for p in parts:
                        if p != title and not company and not any(kw in p.lower() for kw in ("fuzu", "start hiring", "only on")):
                            company = p
                        elif p != title and p != company and "•" in p:
                            location = p

                    opportunities.append(Opportunity(
                        title=title,
                        company=company or "Fuzu",
                        url=url,
                        description=text[:2000],
                        source="fuzu",
                        category="job",
                        remote="Remote" if location and "remote" in location.lower() else "",
                    ))

        except Exception:
            pass

        return opportunities
