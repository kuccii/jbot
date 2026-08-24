import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

BOARDS = [
    {
        "url": "https://www.myjobmag.co.ke/jobs",
        "name": "MyJobMag Kenya",
        "selector": "li[class*='job']",
        "title_tag": ["h2", "h3"],
    },
    {
        "url": "https://www.opportunitiesforafricans.com/",
        "name": "OpportunitiesForAfricans",
        "selector": "h3.magcat-titlte.entry-title",
        "title_tag": ["h3"],
    },
]


@register("african_jobs")
class AfricanJobBoardScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for board in BOARDS:
                try:
                    resp = await client.get(board["url"], headers={"User-Agent": USER_AGENT})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    items = soup.select(board["selector"])

                    for item in items:
                        title_tag = item if item.name in ("h2", "h3", "h4") else item.find(board["title_tag"])
                        title = title_tag.get_text(strip=True) if title_tag else ""
                        if not title or len(title) < 5:
                            continue

                        link_tag = item.find("a", href=True) if item.name != "a" else item
                        href = link_tag.get("href", "") if link_tag else ""
                        full_url = href if href.startswith("http") else f"{resp.url.rstrip('/')}/{href.lstrip('/')}" if href else str(resp.url)
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        text = item.get_text(separator=" ", strip=True)[:1000]

                        opportunities.append(Opportunity(
                            title=title[:500],
                            company=board["name"],
                            url=full_url,
                            description=text[:2000],
                            source="african_jobs",
                            category="job",
                            remote="Remote" if any(k in text.lower() for k in ("remote", "virtual")) else "",
                        ))
                except Exception:
                    continue

        return opportunities
