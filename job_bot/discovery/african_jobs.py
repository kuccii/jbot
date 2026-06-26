import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import is_expired

JOB_BOARD_SOURCES = [
    ("https://www.brightermonday.co.ke/jobs", "BrighterMonday Kenya"),
    ("https://www.myjobmag.co.ke/jobs", "MyJobMag Kenya"),
    ("https://www.careers24.com.za/jobs", "Careers24 South Africa"),
    ("https://www.jobwebafrica.com/jobs", "JobWebAfrica"),
    ("https://www.jobberman.com/jobs", "Jobberman Nigeria"),
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@register("african_jobs")
class AfricanJobBoardScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()
        any_success = False

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for url, name in JOB_BOARD_SOURCES:
                try:
                    resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")

                    items = soup.find_all("article")
                    if not items:
                        items = soup.find_all("div", class_=lambda c: c and any(
                            k in (c or "").lower() for k in ("job", "listing", "card", "post", "item")
                        ))
                    if not items:
                        items = soup.find_all("li", class_=lambda c: c and "job" in (c or "").lower())
                    if not items:
                        items = [soup]

                    any_success = True
                    for item in items:
                        link_tag = item.find("a", href=True) if item != soup else None
                        title_tag = item.find(["h2", "h3", "h4"])
                        title = ""
                        if title_tag:
                            title = title_tag.get_text(strip=True)
                        if not title:
                            title_tag = item.find(["a", "span"], class_=lambda c: c and "title" in (c or "").lower())
                            if title_tag:
                                title = title_tag.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        if link_tag:
                            href = link_tag.get("href", "")
                            full_url = href if href.startswith("http") else f"{resp.url.rstrip('/')}/{href.lstrip('/')}"
                        else:
                            full_url = str(resp.url)

                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        desc_tag = item.find("p")
                        desc = desc_tag.get_text(strip=True) if desc_tag else ""
                        text = item.get_text(separator=" ", strip=True)[:1000]

                        opportunities.append(Opportunity(
                            title=title[:500],
                            company=name,
                            url=full_url,
                            description=(desc or text)[:2000],
                            source="african_jobs",
                            category="job",
                            remote="Remote",
                        ))

                except Exception:
                    continue

        if not any_success:
            opportunities.append(Opportunity(
                title="Browse African Remote Jobs",
                company="BrighterMonday / MyJobMag / Jobberman",
                url="https://www.brightermonday.co.ke/jobs",
                source="african_jobs",
                description="Niche job boards for remote and local roles across Africa.",
                category="job",
                remote="Remote",
            ))

        return opportunities
