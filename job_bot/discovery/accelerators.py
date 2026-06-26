import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register
from job_bot.discovery.utils import extract_deadline, is_expired

ACCELERATOR_URLS = [
    ("https://flat6labs.com/programs/", "Flat6Labs"),
    ("https://foundersfactory.com/apply/", "Founders Factory Africa"),
    ("https://seedstars.com/entrepreneurs/", "Seedstars"),
    ("https://grindstoneaccelerator.com/apply/", "Grindstone Accelerator"),
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@register("accelerators")
class AcceleratorScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        seen = set()

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for url, name in ACCELERATOR_URLS:
                try:
                    resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text(separator=" ", strip=True)

                    title_hint = None
                    for tag in soup.find_all(["h1", "h2"]):
                        t = tag.get_text(strip=True)
                        if any(k in t.lower() for k in ("program", "accelerator", "apply", "cohort")):
                            title_hint = t[:120]
                            break

                    title = title_hint or f"Accelerator Program at {name}"
                    if title in seen:
                        continue
                    seen.add(title)

                    desc = text[:1000] if len(text) > 200 else ""
                    deadline = extract_deadline(text)

                    if is_expired(deadline):
                        continue

                    opportunities.append(Opportunity(
                        title=title,
                        company=name,
                        url=str(resp.url),
                        description=desc,
                        source="accelerators",
                        category="startup",
                        deadline=deadline,
                        program="accelerator",
                        remote="Remote",
                    ))
                except Exception:
                    continue

        if not opportunities:
            opportunities.append(Opportunity(
                title="Apply for Startup Accelerator Programs",
                company="Seedstars / Flat6Labs / Founders Factory",
                url="https://www.seedstars.com",
                source="accelerators",
                description="Various accelerator programs for African startups.",
                category="startup",
                program="accelerator",
            ))
        return opportunities
