import re
import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EUROPE_COUNTRIES = [
    "germany", "france", "uk", "united kingdom", "netherlands", "sweden", "norway",
    "denmark", "finland", "belgium", "switzerland", "austria", "ireland", "spain",
    "italy", "portugal", "luxembourg", "poland", "czech", "croatia", "greece",
]

CITY_COUNTRY_MAP = {
    "berlin": "Germany", "munich": "Germany", "hamburg": "Germany",
    "frankfurt": "Germany", "cologne": "Germany", "stuttgart": "Germany",
    "dusseldorf": "Germany", "dresden": "Germany", "leipzig": "Germany",
    "bremen": "Germany", "hanover": "Germany", "bonn": "Germany",
    "london": "UK", "manchester": "UK", "birmingham": "UK", "edinburgh": "UK",
    "paris": "France", "lyon": "France", "marseille": "France",
    "amsterdam": "Netherlands", "rotterdam": "Netherlands", "the hague": "Netherlands",
    "brussels": "Belgium", "vienna": "Austria", "zurich": "Switzerland",
    "geneva": "Switzerland", "stockholm": "Sweden", "oslo": "Norway",
    "copenhagen": "Denmark", "helsinki": "Finland", "dublin": "Ireland",
    "madrid": "Spain", "barcelona": "Spain", "rome": "Italy", "milan": "Italy",
    "lisbon": "Portugal", "prague": "Czech Republic",
}


def _classify_country(location: str, title: str = "", description: str = "") -> str:
    text = (location + " " + title + " " + description).lower()
    for city, country in CITY_COUNTRY_MAP.items():
        if city in text:
            return country
    for country in EUROPE_COUNTRIES:
        if country in text:
            return country.title()
    if "europe" in text:
        return "Europe"
    return ""


@register("europe_jobs")
class EuropeJobScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        seen_urls = set()

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            jobs = await self._scrape_arbeitnow(client)
            for job in jobs:
                url = job["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                country = _classify_country(job.get("location", ""), job.get("title", ""))
                opportunities.append(Opportunity(
                    title=job["title"][:500],
                    company=job.get("company", ""),
                    url=url,
                    description=job.get("description", "")[:2000],
                    source="europe_jobs",
                    category="job",
                    location=job.get("location", ""),
                    salary_range=job.get("salary", ""),
                    remote=job.get("remote", ""),
                ))

            aa_jobs = await self._scrape_advance_africa_europe(client)
            for job in aa_jobs:
                url = job["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                country = _classify_country(job.get("location", ""), job.get("title", ""))
                opportunities.append(Opportunity(
                    title=job["title"][:500],
                    company=job.get("company", "AdvanceAfrica"),
                    url=url,
                    description=job.get("description", "")[:2000],
                    source="europe_jobs",
                    category="job",
                    location=job.get("location", country or "Europe"),
                    salary_range=job.get("salary", ""),
                ))

        return opportunities

    async def _scrape_arbeitnow(self, client: httpx.AsyncClient) -> list[dict]:
        jobs = []
        try:
            resp = await client.get(
                "https://www.arbeitnow.com/api/job-board-api",
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    tags = [t.lower() for t in item.get("tags", [])]
                    title = item.get("title", "")
                    location = item.get("location", "")
                    if not title or not location:
                        continue
                    country = _classify_country(location, title)
                    if not country:
                        continue
                    desc = item.get("description", "")
                    clean_desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)[:2000]
                    jobs.append({
                        "title": title.strip(),
                        "company": item.get("company_name", "").strip(),
                        "url": item.get("url", ""),
                        "location": f"{location.strip()}, {country}",
                        "description": clean_desc,
                        "remote": "Remote" if "remote" in tags else "",
                        "salary": "",
                        "tags": tags,
                    })
        except Exception:
            pass
        return jobs

    async def _scrape_advance_africa_europe(self, client: httpx.AsyncClient) -> list[dict]:
        jobs = []
        pages = [
            ("https://www.advance-africa.com/Nursing-Jobs.html", "Nursing Jobs in Europe"),
            ("https://www.advance-africa.com/English-Language-Assistants-Jobs-in-France-for-International-Students.html", "Teaching Assistant France"),
            ("https://www.advance-africa.com/Voluntary-Service.html", "Voluntary Service Germany"),
            ("https://www.advance-africa.com/European-Commission-Paid-Traineeships.html", "EU Traineeships"),
        ]
        for url, default_title in pages:
            try:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                body = soup.get_text(separator=" ", strip=True)
                title_tag = soup.find("title")
                title = title_tag.string.strip() if title_tag and title_tag.string else default_title
                country = _classify_country(title, body)
                jobs.append({
                    "title": title[:500],
                    "company": "AdvanceAfrica",
                    "url": url,
                    "location": country or "Europe",
                    "description": body[:2000],
                    "salary": "",
                })
            except Exception:
                continue
        return jobs
