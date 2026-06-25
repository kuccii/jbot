import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import extract_deadline, is_expired

# ── Domain → category mapping ──────────────────────────────────────────────
# Entries whose domain contains any of these strings get the mapped category.
# The default (no match) is "job".
DOMAIN_CATEGORY_MAP: dict[str, str] = {
    # Grant / fellowship / scholarship aggregators
    "opportunitydesk.org": "grant",
    "opportunitiesforafricans.com": "grant",
    "africa-grants.com": "grant",
    "scholarshipsforafricans.com": "grant",
    "menterprise.africa": "grant",
    "devex.com": "grant",
}

# ── Content-level category hints ───────────────────────────────────────────
# If the page <title> or the first 500 chars of visible text match these,
# the opportunity is tagged as "grant" even when the domain is unknown.
GRANT_CONTENT_HINTS = re.compile(
    r"(grant|fellowship|scholarship|funding)",
    re.IGNORECASE,
)

# ── Opportunity keyword patterns ───────────────────────────────────────────
OPPORTUNITY_KEYWORDS = re.compile(
    r"(career|job|position|opening|vacanc|opportunit|apply|hiring|"
    r"work\s*with\s*us|join\s*our\s*team|internship|trainee|"
    r"scholarship|fellowship|grant|funding|program)",
    re.IGNORECASE,
)

# ── Link patterns to skip (noise) ──────────────────────────────────────────
SKIP_URL_PATTERNS = re.compile(
    r"(twitter\.com|facebook\.com|linkedin\.com|instagram\.com|"
    r"youtube\.com|t\.co|x\.com|login|signup|sign.?in|register|"
    r"forgot|password|privacy|cookie|terms)",
    re.IGNORECASE,
)


@register("company_pages")
class CompanyPagesScraper(BaseScraper):
    def __init__(self):
        self.entries: list[str] = []

    def set_companies(self, entries: list[str]):
        self.entries = entries

    # ── URL helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_url(entry: str) -> str:
        entry = entry.strip()
        if entry.startswith(("http://", "https://")):
            return entry
        if "." in entry:
            return f"https://{entry}"
        return f"https://{entry}.com/careers"

    @staticmethod
    def _domain_of(url: str) -> str:
        """Return the lowercase domain, stripped of ``www.``."""
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host

    def _detect_category(self, url: str, page_title: str, page_text: str) -> str:
        """Determine whether a page is a job board, grant site, or startup hub."""
        domain = self._domain_of(url)
        for pattern, cat in DOMAIN_CATEGORY_MAP.items():
            if pattern in domain:
                return cat
        # Content-based fallback – check title + first snippet of text
        if GRANT_CONTENT_HINTS.search(page_title) or GRANT_CONTENT_HINTS.search(page_text[:500]):
            return "grant"
        return "job"

    # ── Core discovery ─────────────────────────────────────────────────────

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        seen_urls: set[str] = set()
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
                    # Grab first ~3 KB of visible text for content sniffing
                    page_text = soup.get_text(separator=" ", strip=True)

                    category = self._detect_category(
                        str(resp.url), page_title, page_text
                    )

                    links_found = 0

                    # ════════════════════════════════════════════════════════
                    # Mode A: <a> tag discovery (all categories)
                    # ════════════════════════════════════════════════════════
                    for a_tag in soup.find_all("a", href=True):
                        text = a_tag.get_text(strip=True)
                        href = a_tag["href"]

                        # --- Filtering rules ---------------------------------
                        # Minimum length – short nav items are rarely listings
                        if len(text) < 10:
                            continue
                        # Skip noise links that dominate the results
                        if SKIP_URL_PATTERNS.search(href) or SKIP_URL_PATTERNS.search(text):
                            continue
                        # Must match at least one opportunity keyword
                        if not OPPORTUNITY_KEYWORDS.search(text) and not OPPORTUNITY_KEYWORDS.search(href):
                            continue

                        full_url = (
                            href
                            if href.startswith("http")
                            else resp.url.join(href).href
                        )

                        # --- Dedup by URL ------------------------------------
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        # --- Deadline extraction -----------------------------
                        # Combine link text + parent text + sibling text
                        parent = a_tag.parent
                        sibling_text = ""
                        if parent:
                            sibling_text = parent.get_text(separator=" ", strip=True)
                        combined_text = f"{text} {sibling_text}"
                        deadline = extract_deadline(combined_text)

                        # --- Skip expired (if deadline found and past) ------
                        if is_expired(deadline):
                            continue

                        opportunities.append(Opportunity(
                            title=text[:200],
                            company=entry,
                            url=full_url,
                            description=page_title,
                            source="company_pages",
                            category=category,
                            deadline=deadline,
                        ))
                        links_found += 1

                    # ════════════════════════════════════════════════════════
                    # Mode B: article-card discovery for grant-type sites
                    # ════════════════════════════════════════════════════════
                    if category == "grant":
                        articles = self._find_article_cards(soup)
                        for article in articles:
                            opp = self._article_to_opportunity(
                                article, entry, str(resp.url), page_title
                            )
                            if opp is None:
                                continue
                            if opp.url in seen_urls:
                                continue
                            if is_expired(opp.deadline):
                                continue
                            seen_urls.add(opp.url)
                            opportunities.append(opp)
                            links_found += 1

                    # --- Intelligent fallback --------------------------------
                    if not links_found:
                        opportunities.append(Opportunity(
                            title=page_title,
                            company=entry,
                            url=url,
                            description=page_title,
                            source="company_pages",
                            category=category,
                        ))

                except Exception:
                    pass
        return opportunities

    # ── Article-card helpers (Mode B) ─────────────────────────────────────

    @staticmethod
    def _find_article_cards(soup: BeautifulSoup) -> list[BeautifulSoup]:
        """Return list of tags that look like article/card listings."""
        articles: list[BeautifulSoup] = []
        articles.extend(soup.find_all("article"))

        card_classes = ("post", "entry", "listing", "card")
        for div in soup.find_all("div", class_=True):
            cls_str = " ".join(div.get("class", [])).lower()
            if any(cc in cls_str for cc in card_classes):
                if div.find(["h1", "h2", "h3", "h4"]) and div.find("a", href=True):
                    articles.append(div)
        return articles

    @staticmethod
    def _article_to_opportunity(
        article: BeautifulSoup, company: str, base_url: str, page_title: str
    ) -> Opportunity | None:
        """Extract an Opportunity from a single article-card element."""
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

        desc_tag = article.find("p") or article.find(
            class_=re.compile(r"excerpt|summary", re.IGNORECASE)
        )
        description = desc_tag.get_text(strip=True) if desc_tag else page_title

        article_text = article.get_text(separator=" ", strip=True)
        deadline = extract_deadline(article_text)

        return Opportunity(
            title=title[:500],
            company=company,
            url=full_url,
            description=description[:2000],
            source="company_pages",
            category="grant",
            deadline=deadline,
        )
