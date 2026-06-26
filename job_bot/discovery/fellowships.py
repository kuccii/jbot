import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import extract_deadline, is_expired

FELLOWSHIP_SOURCES = [
    ("https://mastercardfoundation.org/scholarships/", "Mastercard Foundation"),
    ("https://www.anzishaprize.org/apply/", "Anzisha Prize"),
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@register("fellowships")
class FellowshipScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()
        any_success = False

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for url, source_label in FELLOWSHIP_SOURCES:
                try:
                    resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    articles = soup.find_all("article")
                    if not articles:
                        articles = []
                        for div in soup.find_all("div", class_=True):
                            cls = " ".join(div.get("class", [])).lower()
                            if any(c in cls for c in ("card", "post", "entry", "listing")):
                                if div.find(["h2", "h3"]) and div.find("a", href=True):
                                    articles.append(div)

                    if not articles:
                        text = soup.get_text(separator=" ", strip=True)
                        if len(text) > 100:
                            title_tag = soup.find(["h1", "h2"])
                            title = title_tag.get_text(strip=True)[:200] if title_tag else f"Fellowship at {source_label}"
                            if title not in seen_urls:
                                seen_urls.add(title)
                                deadline = extract_deadline(text)
                                if not is_expired(deadline):
                                    opportunities.append(Opportunity(
                                        title=title,
                                        company=source_label,
                                        url=str(resp.url),
                                        description=text[:2000],
                                        source="fellowships",
                                        category="grant",
                                        deadline=deadline,
                                        remote="Remote",
                                    ))
                            any_success = True
                            continue

                    any_success = True
                    for article in articles:
                        heading = article.find(["h2", "h3", "h4"])
                        if not heading:
                            continue
                        link = heading.find("a", href=True) or article.find("a", href=True)
                        if not link:
                            continue
                        title = heading.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue
                        href = link.get("href", "")
                        full_url = href if href.startswith("http") else f"{resp.url.rstrip('/')}/{href.lstrip('/')}"
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        desc_tag = article.find("p")
                        description = desc_tag.get_text(strip=True) if desc_tag else ""
                        article_text = article.get_text(separator=" ", strip=True)
                        deadline = extract_deadline(article_text)

                        if is_expired(deadline):
                            continue

                        opportunities.append(Opportunity(
                            title=title[:500],
                            company=source_label,
                            url=full_url,
                            description=(description or article_text)[:2000],
                            source="fellowships",
                            category="grant",
                            deadline=deadline,
                            remote="Remote",
                        ))

                except Exception:
                    continue

        if not any_success:
            opportunities.append(Opportunity(
                title="Check Mastercard Foundation for latest scholarships",
                company="Mastercard Foundation",
                url="https://mastercardfdn.org/all-scholarships/",
                source="fellowships",
                description="The Mastercard Foundation Scholars Program provides access to education for African students.",
                category="grant",
            ))
        return opportunities
