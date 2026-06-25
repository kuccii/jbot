import json

import httpx
from bs4 import BeautifulSoup
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("ycombinator")
class YCombinatorScraper(BaseScraper):
    """Scrape Y Combinator startup & job listings.

    Both ``workatastartup.com`` and ``ycombinator.com/jobs`` are
    Next.js applications.  The scraper first tries to extract structured
    data from the ``__NEXT_DATA__`` script tag embedded in the page,
    then falls back to ``application/ld+json`` and finally to known
    JSON API endpoints.
    """

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _find_next_data(soup: BeautifulSoup) -> dict | None:
        """Return the parsed ``__NEXT_DATA__`` payload, if present."""
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                return json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @staticmethod
    def _find_ld_json(soup: BeautifulSoup) -> list[dict]:
        """Return all parsed ``application/ld+json`` blocks."""
        results: list[dict] = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        results.append(data)
                except (json.JSONDecodeError, TypeError):
                    pass
        return results

    # ── targeted parsers ───────────────────────────────────────────────────

    def _parse_workatastartup(self, next_data: dict) -> list[Opportunity]:
        """Extract startup listings from ``workatastartup.com``."""
        ops: list[Opportunity] = []
        try:
            props = next_data.get("props", {}).get("pageProps", {})
            # The companies list lives under various keys depending on the
            # exact route / API snapshot at build time.
            companies = (
                props.get("companies")
                or props.get("companySummaries")
                or props.get("companyList")
                or []
            )
            for c in companies:
                if not isinstance(c, dict):
                    continue
                name = c.get("name", "").strip() or c.get("companyName", "").strip()
                if not name:
                    continue
                tagline = c.get("tagline", "").strip() or c.get("oneLiner", "").strip() or c.get("description", "").strip()
                slug = (c.get("slug") or c.get("id") or "").strip()
                url = c.get("url", "").strip() or c.get("website", "").strip()
                if not url and slug:
                    url = f"https://www.workatastartup.com/companies/{slug}"
                elif not url:
                    url = "https://www.workatastartup.com/companies"

                ops.append(Opportunity(
                    title=f"{name} – {tagline}" if tagline else name,
                    company=name,
                    url=url,
                    description=tagline or name,
                    source="ycombinator",
                    category="startup",
                ))
        except Exception:
            pass
        return ops

    def _parse_yc_jobs(self, next_data: dict) -> list[Opportunity]:
        """Extract job listings from ``ycombinator.com/jobs``."""
        ops: list[Opportunity] = []
        try:
            props = next_data.get("props", {}).get("pageProps", {})
            jobs = (
                props.get("jobs")
                or props.get("jobListings")
                or props.get("jobsList")
                or []
            )
            for j in jobs:
                if not isinstance(j, dict):
                    continue
                title = (j.get("title") or j.get("jobTitle") or "").strip()
                if not title:
                    continue
                # Company can be a nested object or a string
                company_raw = j.get("company", {})
                if isinstance(company_raw, dict):
                    company = (company_raw.get("name") or "").strip()
                else:
                    company = str(company_raw).strip()
                if not company:
                    company = "Y Combinator Startup"

                slug = (j.get("slug") or j.get("id") or "").strip()
                url = f"https://www.ycombinator.com/jobs/{slug}" if slug else "https://www.ycombinator.com/jobs"
                description = (j.get("description") or j.get("tagline") or "").strip()

                ops.append(Opportunity(
                    title=title,
                    company=company,
                    url=url,
                    description=description or title,
                    source="ycombinator",
                    category="startup",
                ))
        except Exception:
            pass
        return ops

    def _parse_ld_json_opportunities(self, ld_items: list[dict]) -> list[Opportunity]:
        """Extract ``JobPosting`` entries from JSON-LD structured data."""
        ops: list[Opportunity] = []
        for item in ld_items:
            if not isinstance(item, dict):
                continue
            if "JobPosting" in item.get("@type", ""):
                org = item.get("hiringOrganization", {}) or {}
                company = (
                    org.get("name", "")
                    if isinstance(org, dict)
                    else str(org)
                ) or "Y Combinator Startup"
                ops.append(Opportunity(
                    title=(item.get("title") or "").strip(),
                    company=company,
                    url=(item.get("url") or "").strip(),
                    description=(item.get("description") or "").strip(),
                    source="ycombinator",
                    category="startup",
                ))
        return ops

    # ── entry point ────────────────────────────────────────────────────────

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0"}

            # ── 1.  workatastartup.com/companies ────────────────────────────
            try:
                resp = await client.get(
                    "https://www.workatastartup.com/companies",
                    headers=headers,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    data = self._find_next_data(soup)
                    if data:
                        opportunities.extend(self._parse_workatastartup(data))
            except Exception:
                pass

            # ── 2.  ycombinator.com/jobs ────────────────────────────────────
            if not opportunities:
                try:
                    resp = await client.get(
                        "https://www.ycombinator.com/jobs",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        data = self._find_next_data(soup)
                        if data:
                            opportunities.extend(self._parse_yc_jobs(data))
                except Exception:
                    pass

            # ── 3.  JSON‑LD fallback ─────────────────────────────────────────
            if not opportunities:
                for page_url in (
                    "https://www.workatastartup.com/companies",
                    "https://www.ycombinator.com/jobs",
                ):
                    try:
                        resp = await client.get(page_url, headers=headers)
                        if resp.status_code != 200:
                            continue
                        soup = BeautifulSoup(resp.text, "html.parser")
                        ld = self._find_ld_json(soup)
                        if ld:
                            opportunities.extend(
                                self._parse_ld_json_opportunities(ld)
                            )
                            if opportunities:
                                break
                    except Exception:
                        continue

        return opportunities
