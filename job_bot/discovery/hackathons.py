from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import extract_deadline, is_expired

HACKATHON_SOURCES = [
    ("https://mlh.io/seasons/2026/events", "MLH"),
    ("https://devpost.com/hackathons", "Devpost"),
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@register("hackathons")
class HackathonScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()
        any_success = False

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for url, source in HACKATHON_SOURCES:
                try:
                    resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")

                    if source == "MLH":
                        items = soup.find_all("div", class_=lambda c: c and "event" in c.lower())
                        if not items:
                            items = soup.find_all("div", class_=lambda c: c and "col-lg-3" in (c or ""))
                        if not items:
                            items = [soup]

                        for item in items:
                            link_tag = item.find("a", href=True)
                            title_tag = item.find(["h3", "h4", "h5", "strong"])
                            title = ""
                            if title_tag:
                                title = title_tag.get_text(strip=True)
                            if not title:
                                title_tag = item.find(["p", "span"])
                                if title_tag:
                                    title = title_tag.get_text(strip=True)
                            if not title:
                                continue

                            href = link_tag.get("href", "") if link_tag else ""
                            full_url = href if href.startswith("http") else f"https://mlh.io{href}"

                            if full_url in seen_urls:
                                continue
                            seen_urls.add(full_url)

                            desc_tag = item.find("p")
                            desc = desc_tag.get_text(strip=True) if desc_tag else ""
                            text = item.get_text(separator=" ", strip=True)
                            deadline = extract_deadline(text)

                            if is_expired(deadline):
                                continue

                            opportunities.append(Opportunity(
                                title=title[:300],
                                company="MLH",
                                url=full_url or url,
                                description=(desc or text)[:2000],
                                source="hackathons",
                                category="startup",
                                deadline=deadline,
                                remote="Remote",
                            ))
                            any_success = True

                    else:
                        items = soup.find_all("article")
                        if not items:
                            items = soup.find_all("div", class_=lambda c: c and ("challenge" in c.lower() or "card" in c.lower()))

                        for item in items:
                            link_tag = item.find("a", href=True)
                            title_tag = item.find(["h2", "h3", "h4"])
                            if not title_tag:
                                continue
                            title = title_tag.get_text(strip=True)
                            if not title or len(title) < 3:
                                continue
                            href = link_tag.get("href", "") if link_tag else ""
                            full_url = href if href.startswith("http") else urljoin(url, href)

                            if full_url in seen_urls:
                                continue
                            seen_urls.add(full_url)

                            desc_tag = item.find("p")
                            desc = desc_tag.get_text(strip=True) if desc_tag else ""
                            text = item.get_text(separator=" ", strip=True)
                            deadline = extract_deadline(text)

                            if is_expired(deadline):
                                continue

                            opportunities.append(Opportunity(
                                title=title[:300],
                                company="Devpost",
                                url=full_url,
                                description=(desc or text)[:2000],
                                source="hackathons",
                                category="startup",
                                deadline=deadline,
                                remote="Remote",
                            ))
                            any_success = True

                except Exception:
                    continue

        if not any_success:
            opportunities.append(Opportunity(
                title="Participate in MLH Hackathons",
                company="Major League Hacking",
                url="https://mlh.io/seasons/2026/events",
                source="hackathons",
                description="MLH runs weekend-long hackathons for developers worldwide.",
                category="startup",
                program="hackathon",
                remote="Remote",
            ))
        return opportunities
