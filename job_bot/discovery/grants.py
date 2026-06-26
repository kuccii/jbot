"""
Scraper for grant / fellowship / opportunity-aggregator websites.

Fetches article-style listings from known WordPress-based aggregators and
extracts title, description, URL, and deadline for each entry.  Expired
listings (deadline in the past) are dropped automatically.
"""

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import extract_deadline, is_expired

# ── Grant aggregator sites ───────────────────────────────────────────────────
# Each entry is (url, source_label).  The scraper fetches the HTML, looks for
# article-card patterns common to WordPress sites, and extracts listings.

GRANT_SOURCES: list[tuple[str, str]] = [
    ("https://www.opportunitydesk.org/category/grants/", "opportunitydesk.org"),
    ("https://www.opportunitiesforafricans.com/category/fellowships/", "opportunitiesforafricans.com"),
    ("https://www.opportunitiesforafricans.com/category/grants/", "opportunitiesforafricans.com"),
    ("https://menterprise.africa/category/grants/", "menterprise.africa"),
    ("https://www.fundsforngos.org/", "fundsforngos.org"),
    ("https://www.developpp.de/en/application/ventures", "develoPPP Ventures"),
    ("https://invest-for-jobs.com/en/calls-for-proposals-overview", "Invest for Jobs"),
    ("https://vc4a.com/developpp/2025-q2/", "VC4A develoPPP"),
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


@register("grants")
class GrantScraper(BaseScraper):
    """Scrape grant / fellowship listings from aggregator WordPress sites."""

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        seen_urls: set[str] = set()
        any_success = False

        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True
        ) as client:
            for url, source in GRANT_SOURCES:
                try:
                    resp = await client.get(
                        url, headers={"User-Agent": USER_AGENT}
                    )
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    articles = self._find_articles(soup)
                    if not articles:
                        continue

                    any_success = True

                    for article in articles:
                        opp = self._article_to_opportunity(
                            article, source, str(resp.url)
                        )
                        if opp is None:
                            continue
                        if opp.url in seen_urls:
                            continue
                        # Skip expired
                        if is_expired(opp.deadline):
                            continue
                        seen_urls.add(opp.url)
                        opportunities.append(opp)

                except Exception:
                    continue  # Try next source

        # ── Fallback ────────────────────────────────────────────────────────
        if not any_success:
            opportunities.append(self._placeholder())

        return opportunities

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _find_articles(soup: BeautifulSoup) -> list[BeautifulSoup]:
        """Return a list of tag objects that look like article/card listings."""
        articles: list[BeautifulSoup] = []

        # 1. Native <article> tags
        articles.extend(soup.find_all("article"))

        # 2. <div> elements whose class contains post/entry/listing/card
        card_classes = ("post", "entry", "listing", "card")
        for div in soup.find_all("div", class_=True):
            classes = set(div.get("class", []))
            cls_str = " ".join(classes).lower()
            if any(cc in cls_str for cc in card_classes):
                # Make sure it has a heading + link (looks like a listing)
                if div.find(["h1", "h2", "h3", "h4"]) and div.find("a", href=True):
                    articles.append(div)

        return articles

    @staticmethod
    def _article_to_opportunity(
        article: BeautifulSoup, source: str, base_url: str
    ) -> Opportunity | None:
        """Extract an ``Opportunity`` from a single article-card element."""
        # ── Title & URL ─────────────────────────────────────────────────────
        heading = article.find(["h1", "h2", "h3", "h4"])
        if not heading:
            return None
        link = heading.find("a", href=True) or article.find("a", href=True)
        if not link:
            return None

        title = heading.get_text(strip=True)
        if not title or len(title) < 5:
            return None

        href = link.get("href", "")
        full_url = href if href.startswith("http") else urljoin(base_url, href)

        # ── Description ─────────────────────────────────────────────────────
        desc_tag = article.find("p") or article.find(
            class_=re.compile(r"excerpt|summary", re.IGNORECASE)
        )
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # ── Deadline ────────────────────────────────────────────────────────
        article_text = article.get_text(separator=" ", strip=True)
        deadline = extract_deadline(article_text)

        return Opportunity(
            title=title[:500],
            company=source,
            url=full_url,
            description=description[:2000],
            source="grants",
            category="grant",
            deadline=deadline,
        )

    @staticmethod
    def _placeholder() -> Opportunity:
        """Return a single fallback entry when scraping fails entirely."""
        return Opportunity(
            title="Check grants.gov for latest grants",
            company="grants.gov",
            url="https://www.grants.gov/web/grants/search-grants.html",
            source="grants",
            description="Visit grants.gov for current grant opportunities.",
            category="grant",
        )
