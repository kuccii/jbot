import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

BOARDS = [
    {
        "url": "https://www.jobinrwanda.com/",
        "source": "jobinrwanda",
        "name": "JobinRwanda",
        "selector": ".card-body.p-2",
        "link_selector": "a",
        "company_selector": "p.card-text a[href^='/employer/']",
    },
    {
        "url": "https://greatrwandajobs.com/jobs",
        "source": "greatrwandajobs",
        "name": "GreatRwandaJobs",
        "selector": ".js-data a[href*='job-detail']",
        "link_selector": None,
        "company_from_title": True,
    },
    {
        "url": "https://www.brightermonday.co.rw/jobs",
        "source": "brightermonday",
        "name": "BrighterMonday",
        "selector": "a[href*='/listings/']",
        "link_selector": None,
        "card_selector": "div.w-full",
        "company_selector": "p.text-sm.text-blue-700.text-loading-animate.inline-block.mt-3",
        "max_pages": 29,
    },
    {
        "url": "https://www.advance-africa.com/Jobs-in-Rwanda.html",
        "source": "advanceafrica",
        "name": "AdvanceAfrica",
        "selector": "a[href*='.html']",
        "link_selector": None,
        "company_from_title": True,
        "filter": lambda t: len(t) > 15 and (any(kw in t.lower() for kw in ["-jobs-", "-vacanc-", "-career-"]) or "jobs in rwanda" in t.lower()),
    },
]


def _extract_grj_company(title: str) -> str:
    m = re.search(r'\s+job\s+at\s+(.+)', title, re.IGNORECASE)
    return m.group(1).strip() if m else "GreatRwandaJobs"


_AA_ROLE_INDICATORS = {
    "inventory", "procurement", "video", "creative", "senior", "junior", "assistant",
    "intern", "manager", "specialist", "officer", "coordinator", "lead", "associate",
    "logistics", "design", "research", "scientist", "general", "counsel", "global",
    "product", "accounting", "legal", "forest", "plant", "nutrient", "agroforestry",
    "seed", "technology", "tone", "flr", "data", "biofortified", "nursing", "relationship",
    "sales", "strategy", "association", "engagement", "communication",
}


def _extract_aa_company(title: str) -> str:
    text = title.replace(" - Apply", " Apply").split(" Apply")[0].strip()
    text = text.split("Deadline")[0].strip()
    m = re.match(r'^(.*?)\s+Jobs?\s+in\s+Rwanda', text, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        parts = raw.split()
        idx = 1
        while idx < len(parts) and parts[idx].strip(",-").lower() not in _AA_ROLE_INDICATORS:
            idx += 1
        if idx > 1:
            return " ".join(parts[:idx])
        return " ".join(parts[:min(3, len(parts))])
    m = re.match(r'^(.*?)\s+Jobs?\s', text, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        parts = raw.split()
        idx = 1
        while idx < len(parts) and parts[idx].strip(",-").lower() not in _AA_ROLE_INDICATORS:
            idx += 1
        if idx > 1:
            return " ".join(parts[:idx])
        return " ".join(parts[:min(3, len(parts))])
    parts = text.split()
    return " ".join(parts[:3]) if parts else "AdvanceAfrica"


@register("rwanda_jobs")
class RwandaJobBoardScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for board in BOARDS:
                source = board.get("source", "rwanda_jobs")
                try:
                    pages = range(1, board.get("max_pages", 1) + 1)
                    for page in pages:
                        page_url = board["url"]
                        if "max_pages" in board and page > 1:
                            sep = "&" if "?" in page_url else "?"
                            page_url = f"{page_url}{sep}page={page}"

                        resp = await client.get(page_url, headers={"User-Agent": USER_AGENT})
                        if resp.status_code != 200:
                            if "max_pages" in board and page > 1:
                                break
                            continue
                        soup = BeautifulSoup(resp.text, "html.parser")

                        if board.get("card_selector"):
                            cards = soup.select(board["card_selector"])
                            company_sel = board.get("company_selector")
                            for card in cards:
                                link_el = card.select_one(board["selector"])
                                if not link_el:
                                    continue
                                title = link_el.get_text(strip=True)
                                if not title or len(title) < 5:
                                    continue
                                href = link_el.get("href", "")
                                full_url = urljoin(str(resp.url), href) if href else str(resp.url)
                                if full_url in seen_urls:
                                    continue
                                seen_urls.add(full_url)
                                company = board["name"]
                                if company_sel:
                                    ce = card.select_one(company_sel)
                                    if ce:
                                        company = ce.get_text(strip=True)
                                text = card.get_text(separator=" ", strip=True)[:1000]

                                opportunities.append(Opportunity(
                                    title=title[:500],
                                    company=company,
                                    url=full_url,
                                    description=text[:2000],
                                    source=source,
                                    category="job",
                                    location="Rwanda",
                                ))
                        else:
                            items = soup.select(board["selector"])
                            for item in items:
                                link_el = item if board["link_selector"] is None else item.select_one(board["link_selector"])
                                if not link_el:
                                    continue
                                title = link_el.get_text(strip=True)
                                if not title or len(title) < 5:
                                    continue

                                board_filter = board.get("filter")
                                if board_filter and not board_filter(title):
                                    continue

                                href = link_el.get("href", "")
                                full_url = urljoin(str(resp.url), href) if href else str(resp.url)
                                if full_url in seen_urls:
                                    continue
                                seen_urls.add(full_url)

                                company = board["name"]
                                if board.get("company_from_title"):
                                    if source == "greatrwandajobs":
                                        company = _extract_grj_company(title)
                                    elif source == "advanceafrica":
                                        company = _extract_aa_company(title)
                                if board.get("company_selector"):
                                    ce = item.select_one(board["company_selector"])
                                    if ce:
                                        company = ce.get_text(strip=True)

                                text = item.get_text(separator=" ", strip=True)[:1000]

                                opportunities.append(Opportunity(
                                    title=title[:500],
                                    company=company,
                                    url=full_url,
                                    description=text[:2000],
                                    source=source,
                                    category="job",
                                    location="Rwanda",
                                ))

                        if "max_pages" in board:
                            pagination_links = soup.find_all("a", href=True)
                            max_available = page
                            for pl in pagination_links:
                                pt = pl.get_text(strip=True)
                                if pt.isdigit():
                                    max_available = max(max_available, int(pt))
                            if page >= max_available:
                                break

                except Exception:
                    continue

        return opportunities
