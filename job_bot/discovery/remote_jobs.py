import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

BOARDS = [
    {
        "url": "https://weworkremotely.com/categories/remote-back-end-programming-jobs",
        "name": "WeWorkRemotely",
        "selector": ".new-listing-container",
        "title_selector": ".new-listing__header__title__text",
        "link_selector": "a.listing-link--unlocked",
        "company_selector": ".new-listing__company-name",
    },
    {
        "url": "https://remotive.com/remote-jobs",
        "name": "Remotive",
        "selector": ".job-tile",
        "title_selector": ".job-tile-title",
        "link_selector": "a[href*='/remote-jobs/']",
        "skip_first": True,
    },
]


@register("remote_jobs")
class RemoteJobBoardScraper(BaseScraper):
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

                    for idx, item in enumerate(items):
                        if board.get("skip_first") and idx == 0:
                            continue

                        link_el = item.select_one(board["link_selector"])
                        if not link_el:
                            continue

                        title_el = item.select_one(board["title_selector"])
                        title = title_el.get_text(strip=True) if title_el else ""
                        if not title or len(title) < 5:
                            continue

                        href = link_el.get("href", "")
                        full_url = urljoin(str(resp.url), href) if href else str(resp.url)
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        company = board["name"]
                        if board.get("company_selector"):
                            comp_el = item.select_one(board["company_selector"])
                            if comp_el:
                                company = comp_el.get_text(strip=True) or company

                        text = item.get_text(separator=" ", strip=True)[:1000]

                        opportunities.append(Opportunity(
                            title=title[:500],
                            company=company,
                            url=full_url,
                            description=text[:2000],
                            source="remote_jobs",
                            category="job",
                            remote="Remote",
                        ))
                except Exception:
                    continue

        return opportunities
