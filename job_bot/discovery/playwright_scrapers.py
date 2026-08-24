from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


@register("rwanda_playwright")
class RwandaPlaywrightScraper(BaseScraper):
    supported: list[str] = []

    @classmethod
    def _init_class(cls):
        if not HAS_PLAYWRIGHT:
            return
        cls.supported = ["elitejobs"]

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not HAS_PLAYWRIGHT:
            return []

        opportunities = []
        seen_urls = set()

        try:
            jobs = await self._scrape_elitejobs()
            for job in jobs:
                url = job.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                opportunities.append(Opportunity(
                    title=job.get("title", "")[:500],
                    company=job.get("company", "EliteJobs"),
                    url=url,
                    description=job.get("description", "")[:2000],
                    source="elitejobs",
                    category="job",
                    location=job.get("location", "Rwanda"),
                ))
        except Exception:
            pass

        return opportunities

    async def _scrape_elitejobs(self) -> list[dict]:
        jobs = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto("https://elitejobs.rw/jobs", timeout=30000)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)

                links = await page.query_selector_all('a[href^="/jobs/"]')
                for link in links:
                    text = await link.inner_text()
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    full_url = f"https://elitejobs.rw{href}"

                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    title = ""
                    location = ""
                    desc_lines = []

                    for i, line in enumerate(lines):
                        lower = line.lower()
                        # Title is the line after "Easy Apply"
                        if i > 0 and lines[i-1] == "Easy Apply" and line != "Easy Apply":
                            title = line
                            continue
                        if title and not location and ("kigali" in lower or "rwanda" in lower):
                            location = line
                            continue
                        if title and line:
                            skip = {"view", "easy apply", "featured", "urgent", "closes in"}
                            if lower.strip() not in skip and not lower.startswith(("about ", "docs", "applied")):
                                desc_lines.append(line)

                    desc = " | ".join(desc_lines) if desc_lines else text[:500]

                    jobs.append({
                        "title": title if title else lines[0] if lines else "EliteJobs Position",
                        "company": "EliteJobs",
                        "url": full_url,
                        "location": location if location else "Rwanda",
                        "description": desc,
                    })
            finally:
                await browser.close()
        return jobs
