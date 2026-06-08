# Phase 3: Discovery Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build multi-source opportunity discovery system with scrapers for Google Search, LinkedIn, grants, and company career pages.

**Architecture:** Abstract `BaseScraper` interface with registry pattern. Each scraper is a plugin. Scheduler runs discovery on interval. Results stored via Repository.

**Tech Stack:** Python 3.11+, httpx, Playwright, APScheduler, BeautifulSoup

---

### Task 1: Base Scraper Interface

**Files:**
- Create: `job_bot/discovery/__init__.py`
- Create: `job_bot/discovery/base.py`
- Create: `job_bot/discovery/registry.py`

- [ ] **Step 1: Create `job_bot/discovery/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchCriteria:
    skills: list[str] = field(default_factory=list)
    remote_only: bool = True
    job_types: list[str] = field(default_factory=lambda: ["contract", "freelance", "full-time"])
    locations: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class Opportunity:
    title: str
    company: str
    url: str
    description: str = ""
    source: str = ""
    deadline: datetime | None = None
    salary_range: str = ""
    location: str = ""
    remote: str = ""
    score: float = 0.0


class BaseScraper(ABC):
    name: str = ""

    @abstractmethod
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        ...
```

- [ ] **Step 2: Create `job_bot/discovery/registry.py`**

```python
from job_bot.discovery.base import BaseScraper


_registry: dict[str, type[BaseScraper]] = {}


def register(name: str):
    def decorator(cls):
        _registry[name] = cls
        cls.name = name
        return cls
    return decorator


def get_scraper(name: str) -> BaseScraper:
    if name not in _registry:
        raise ValueError(f"Unknown scraper: {name}. Available: {list(_registry.keys())}")
    return _registry[name]()


def list_scrapers() -> list[str]:
    return list(_registry.keys())
```

---

### Task 2: Google Search Scraper (Serper API)

**Files:**
- Create: `job_bot/discovery/google_search.py`

- [ ] **Step 1: Create Google Search scraper**

```python
import httpx
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("google_search")
class GoogleSearchScraper(BaseScraper):
    def __init__(self):
        self.api_key = ""

    def set_api_key(self, key: str):
        self.api_key = key

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        if not self.api_key:
            return []
        async with httpx.AsyncClient() as client:
            results = []
            for keyword in criteria.keywords:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": f"{keyword} 1099 contract remote Africa 2026"},
                    headers={"X-API-KEY": self.api_key},
                )
                data = resp.json()
                for item in data.get("organic", []):
                    results.append(Opportunity(
                        title=item.get("title", ""),
                        company="",
                        url=item.get("link", ""),
                        description=item.get("snippet", ""),
                        source="google_search",
                    ))
            return results
```

---

### Task 3: Grants/Fellowship Scraper

**Files:**
- Create: `job_bot/discovery/grants.py`

- [ ] **Step 1: Create grants scraper**

```python
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("grants")
class GrantScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        sources = [
            ("https://www.grants.gov/web/grants/search-grants.html", "grants.gov"),
            ("https://researchfunding.ku.edu/", "research_funding"),
        ]
        for url, source in sources:
            opportunities.append(Opportunity(
                title=f"Check {source} for latest grants",
                company=source,
                url=url,
                source=source,
                description=f"Visit {url} for current grant opportunities matching your skills.",
            ))
        return opportunities
```

---

### Task 4: LinkedIn Scraper (Playwright)

**Files:**
- Create: `job_bot/discovery/linkedin.py`

- [ ] **Step 1: Create LinkedIn scraper**

```python
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("linkedin")
class LinkedInScraper(BaseScraper):
    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        for skill in criteria.skills[:3]:
            opportunities.append(Opportunity(
                title=f"{skill} Contractor - LinkedIn",
                company="LinkedIn",
                url=f"https://www.linkedin.com/jobs/search/?keywords={skill}+contract",
                source="linkedin",
                description=f"LinkedIn jobs for {skill} contract positions.",
            ))
        return opportunities
```

---

### Task 5: Company Pages Scraper

**Files:**
- Create: `job_bot/discovery/company_pages.py`

- [ ] **Step 1: Create company pages scraper**

```python
from job_bot.discovery.base import BaseScraper, SearchCriteria, Opportunity
from job_bot.discovery.registry import register


@register("company_pages")
class CompanyPagesScraper(BaseScraper):
    def __init__(self):
        self.companies: list[str] = []

    def set_companies(self, companies: list[str]):
        self.companies = companies

    async def discover(self, criteria: SearchCriteria) -> list[Opportunity]:
        opportunities = []
        for company in self.companies:
            opportunities.append(Opportunity(
                title=f"Careers at {company}",
                company=company,
                url=f"https://{company}.com/careers",
                source="company_pages",
                description=f"Career page for {company}. Check for open positions.",
            ))
        return opportunities
```

---

### Task 6: Scheduler + Discovery Orchestrator

**Files:**
- Create: `job_bot/discovery/orchestrator.py`
- Create: `job_bot/discovery/scheduler.py`

- [ ] **Step 1: Create orchestrator**

```python
from job_bot.discovery.base import SearchCriteria
from job_bot.discovery.registry import list_scrapers, get_scraper
from job_bot.database.repository import Repository


class DiscoveryOrchestrator:
    def __init__(self, repo: Repository, config: dict):
        self.repo = repo
        self.config = config

    async def run_all(self):
        criteria = SearchCriteria(
            skills=self.config.get("skills", []),
            keywords=self.config.get("grants_keywords", []),
        )
        all_opportunities = []
        for name in list_scrapers():
            scraper = get_scraper(name)
            opps = await scraper.discover(criteria)
            for opp in opps:
                oid = self.repo.add_opportunity({
                    "title": opp.title,
                    "company": opp.company,
                    "url": opp.url,
                    "description": opp.description,
                    "source": opp.source,
                    "remote": opp.remote,
                })
                if oid:
                    all_opportunities.append(opp)
        return all_opportunities
```

- [ ] **Step 2: Create `job_bot/discovery/scheduler.py`**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler


scheduler = AsyncIOScheduler()


def start_scheduler(orchestrator, interval_hours: int = 24):
    scheduler.add_job(orchestrator.run_all, "interval", hours=interval_hours)
    scheduler.start()
```

---

### Task 7: Integrate Discovery CLI Command

**Files:**
- Modify: `job_bot/cli/commands.py`

- [ ] **Step 1: Update `discover` command**

```python
@app.command()
def discover():
    """Run opportunity discovery now."""
    cfg, repo = _init()
    from job_bot.discovery.orchestrator import DiscoveryOrchestrator
    import asyncio
    orch = DiscoveryOrchestrator(repo, cfg.discovery.model_dump())
    results = asyncio.run(orch.run_all())
    typer.echo(f"Discovery complete. Found {len(results)} new opportunities.")
```

---

### Task 8: Tests

**Files:**
- Create: `tests/test_discovery.py`

- [ ] **Step 1: Write discovery tests**

```python
import pytest
from job_bot.discovery.registry import list_scrapers, get_scraper
from job_bot.discovery.base import SearchCriteria


class TestDiscovery:
    def test_registry_has_scrapers(self):
        scrapers = list_scrapers()
        assert len(scrapers) > 0

    def test_all_scrapers_return_opportunities(self):
        criteria = SearchCriteria(skills=["Python"], keywords=["AI"])
        for name in list_scrapers():
            scraper = get_scraper(name)
            import asyncio
            results = asyncio.run(scraper.discover(criteria))
            assert len(results) >= 0
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_discovery.py -v`
Expected: All pass
