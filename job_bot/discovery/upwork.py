"""Upwork scraper — fetches jobs via Playwright browser (Cloudflare bypass) or httpx fallback."""
import re
import logging
from datetime import datetime, timedelta, timezone

from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.upwork.com/nx/jobs/search/?q={keywords}&sort=recency"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def strip_html(text: str, max_len: int = 2000) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()[:max_len]


def parse_upwork_date(text: str) -> datetime | None:
    """Parse relative Upwork dates like 'Posted 2 hours ago', 'Posted 3 days ago'."""
    if not text:
        return None
    text = text.lower().strip()
    now = datetime.now(timezone.utc)
    m = re.search(r"(\d+)\s*(hour|day|week|month|minute)", text)
    if not m:
        return None
    num = int(m.group(1))
    unit = m.group(2)
    if "minute" in unit:
        td = timedelta(minutes=num)
    elif "hour" in unit:
        td = timedelta(hours=num)
    elif "day" in unit:
        td = timedelta(days=num)
    elif "week" in unit:
        td = timedelta(weeks=num)
    elif "month" in unit:
        td = timedelta(days=num * 30)
    else:
        return None
    return now - td


@register("upwork")
class UpworkScraper(BaseScraper):
    def __init__(self) -> None:
        self._playwright_available: bool | None = None

    def _check_playwright(self) -> bool:
        if self._playwright_available is not None:
            return self._playwright_available
        try:
            import playwright.async_api  # noqa: F401
            self._playwright_available = True
        except ImportError:
            self._playwright_available = False
        return self._playwright_available

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        keywords = criteria.keywords or ["Python", "AI", "Data Science"]
        query = "+".join(kw.replace(" ", "%20") for kw in keywords[:3])

        if self._check_playwright():
            return await self._discover_playwright(query)
        return await self._discover_httpx(query)

    async def _discover_playwright(self, query: str) -> list[Opportunity]:
        try:
            from playwright.async_api import async_playwright

            url = SEARCH_URL.format(keywords=query)
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    content = await page.content()
                    # Check for Cloudflare
                    if "challenge" in content[:2000].lower():
                        logger.warning("Upwork: Cloudflare challenge detected (Playwright headless)")
                        return []

                    # Wait for job cards to render
                    await page.wait_for_selector("[class*=job-tile], [class*=job-card], article", timeout=10000)
                    content = await page.content()
                except Exception:
                    content = await page.content()

                await browser.close()

            return self._parse_html(content, url)

        except Exception as e:
            logger.warning("Upwork Playwright failed: %s", e)
            return []

    async def _discover_httpx(self, query: str) -> list[Opportunity]:
        try:
            import httpx
            from bs4 import BeautifulSoup

            url = SEARCH_URL.format(keywords=query)
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                if resp.status_code != 200:
                    return []
                if "challenge" in resp.text[:2000].lower():
                    logger.info("Upwork: Cloudflare challenge (httpx)")
                    return []
                return self._parse_html(resp.text, url)
        except Exception as e:
            logger.warning("Upwork httpx failed: %s", e)
            return []

    def _parse_html(self, html: str, base_url: str) -> list[Opportunity]:
        """Parse job listings from Upwork search page HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        opportunities = []
        seen_urls = set()

        # Try multiple selectors for job cards
        job_cards = soup.select("[class*=job-tile], [class*=job-card], article, [data-test*=JobTile]")
        if not job_cards:
            # Fall back to searching for job-like div patterns
            job_cards = soup.find_all("div", class_=re.compile(r"(job|Job|tile|Tile)"))

        for card in job_cards:
            try:
                title_el = card.find(["h2", "h3", "h4", "a"], class_=re.compile(r"(title|Title|job-title|JobTitle)"))
                if not title_el:
                    title_el = card.find("a", href=re.compile(r"/jobs/~"))
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                # Get job URL
                job_url = ""
                a_tag = title_el if title_el.name == "a" else title_el.find("a")
                if a_tag and a_tag.get("href"):
                    href = a_tag["href"]
                    job_url = href if href.startswith("http") else f"https://www.upwork.com{href}"

                if not job_url or job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                # Description
                desc_el = card.find(class_=re.compile(r"(description|Description|desc|Desc)"))
                desc = desc_el.get_text(strip=True) if desc_el else ""

                # Posted date
                date_el = card.find(class_=re.compile(r"(posted|Posted|date|Date|caption|Caption)"))
                date_str = date_el.get_text(strip=True) if date_el else ""
                deadline = parse_upwork_date(date_str)

                # Company (Upwork itself)
                company = "Upwork"

                # Budget/salary
                budget_el = card.find(class_=re.compile(r"(budget|Budget|rate|Rate|amount|Amount)"))
                salary_range = budget_el.get_text(strip=True) if budget_el else ""

                # Remote tag
                remote_el = card.find(class_=re.compile(r"(remote|Remote|location|Location)"))
                remote = remote_el.get_text(strip=True) if remote_el else "Remote"

                opportunities.append(Opportunity(
                    title=title[:500],
                    company=company,
                    url=job_url,
                    description=desc[:2000],
                    source="upwork",
                    category="job",
                    deadline=deadline,
                    salary_range=salary_range[:200],
                    remote=remote[:100],
                ))
            except Exception:
                continue

        return opportunities
