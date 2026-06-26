# Implementation Plan: JBot Improvements

## Overview

Based on findings from comparing JBot with career-ops and diagnostics of the live VPS,
this plan addresses seven areas of improvement in dependency order:

1. **Foundation** — Declarative config, canonical statuses, data model cleanup
2. **Fix Existing Data** — Repair category mislabeling, dedup, clean broken records
3. **ATS Discovery Providers** — Direct API scraping for Greenhouse/Lever/Ashby
4. **Liveness Check** — Verify postings still live before scoring
5. **Multi-Dim Scoring** — Replace single 0-100 with 6-dimensional prose scoring
6. **Batch Review + Dashboard** — Better review queue with sort/filter
7. **Comprehensive Tests** — Test coverage for all new and existing code

Each phase is independently deployable and testable.

### VPS Constraints
- 7.8GB RAM total, ~3GB available on host (container uses ~120MB)
- 96GB disk, 8GB free (88% used) — be mindful of disk writes
- NVIDIA Nim `meta/llama-3.3-70b-instruct` as LLM provider
- Serper API key for web search
- SQLite database at `/app/data/job_bot.db`

### Key Diagnostics Findings
- 607 total opportunities, 328 from google_search (ALL mislabeled as category="job")
- 100 twitter entries with broken profile/search URLs
- ALL 607 records have NULL scores (review has never run successfully)
- 20+ groups of duplicate titles from repeated search queries
- No dedup beyond exact URL match
- LinkedIn, YC scrapers disabled in production config

---

## Phase 0: Foundation — Declarative Config + Canonical Statuses

**Goal**: Establish data model and configuration foundation that all subsequent phases build on.

### Dependencies
- None. This is the foundation.

### Files to Create
- `job_bot/discovery/sources.py` — Source config model + loader
- `data/sources.yaml` — Default source definitions

### Files to Modify
- `job_bot/database/models.py` — Add canonical status enum, multi-dim score columns
- `job_bot/database/repository.py` — Support new statuses, liveness column
- `job_bot/config.py` — Add `sources_path` config key
- `job_bot/config_default.yaml` — Add sources_path default
- `job_bot/discovery/registry.py` — Add source metadata support

### Implementation Steps

#### Step 0.1: Add canonical statuses to models.py

```python
# Add to database/models.py

import enum

class OpportunityStatus(str, enum.Enum):
    NEW = "new"
    EVALUATED = "evaluated"
    LIVE_CHECKED = "live_checked"
    DEAD = "dead"
    APPLIED = "applied"
    RESPONDED = "responded"
    REJECTED = "rejected"
    ACCEPTED = "accepted"

# Add to Opportunity model:
#   status = Column(String(50), default=OpportunityStatus.NEW, index=True)
#   liveness_checked_at = Column(DateTime, nullable=True)
#   liveness_status = Column(String(20), nullable=True)  # "live", "dead", "unknown"
#   score_compensation = Column(Float, nullable=True)
#   score_culture = Column(Float, nullable=True)
#   score_legitimacy = Column(Float, nullable=True)
#   score_cv_match = Column(Float, nullable=True)
#   score_red_flags = Column(Float, nullable=True)
#   score_global = Column(Float, nullable=True)
#   score_prose = Column(Text, nullable=True)
```

- Keep `score` column as composite/cached average of 6 dimensions
- Add `opportunity_status` index migration
- The migration is a single ALTER TABLE for SQLite (add columns, no DROP)

#### Step 0.2: Create sources.py

```python
# job_bot/discovery/sources.py

from pydantic import BaseModel
from typing import Optional

class ProviderConfig(BaseModel):
    """Configuration for a single discovery provider."""
    enabled: bool = True
    type: str = "serper"  # "serper", "ats_direct", "rss", "html"
    queries: list[str] = []
    companies: list[str] = []
    label: str = ""

class SourcesConfig(BaseModel):
    providers: dict[str, ProviderConfig] = {}
```

Default `sources.yaml` centrally defines what each scraper searches for,
instead of hardcoding queries inside each scraper.

#### Step 0.3: Modify config.py

```python
# Add to Config
class DiscoveryConfig(BaseModel):
    # ... existing fields ...
    sources_path: str = "data/sources.yaml"
```

#### Step 0.4: Update repository.py

- Add `update_opportunity_liveness(opp_id, status)` method
- Add `get_new_opportunities(limit, category)` method
- Add `get_opportunities_by_status(status)` method
- Add `update_opportunity_scores(opp_id, scores_dict)` method

### Testing
- Test status enum values and transitions
- Test sources.yaml loading and validation
- Test new repository methods with in-memory SQLite
- Verify old status values still work (backward compat)

### Deployment
- Config change only, no Docker rebuild needed
- Run migration script on VPS to add columns
- Create default `sources.yaml` on VPS

### Estimated Effort: 2 days

---

## Phase 1: Fix Existing Data

**Goal**: Repair the 328 mislabeled google_search records, clean duplicate titles,
and fix broken twitter URLs.

### Dependencies
- Phase 0 — needs canonical statuses and new columns

### Files to Create
- `scripts/repair_data.py` — One-time data migration/fix script

### Files to Modify
- `job_bot/discovery/google_search.py` — Add category detection via content classifier
- `job_bot/discovery/linkedin.py` — Already has `_categorize()`, keep it
- `job_bot/discovery/twitter.py` — Fix URL generation, dedup broken entries
- `job_bot/discovery/orchestrator.py` — Add dedup by normalized title

### Implementation Steps

#### Step 1.1: Fix google_search.py category detection

Replace the hardcoded `category="job"` with content-based categorization.
Use the same pattern as linkedin.py's `_categorize()`:

```python
def _categorize(self, title: str, snippet: str) -> str:
    text = (title + " " + snippet).lower()
    if any(w in text for w in ("grant", "funding", "fellowship", "scholarship")):
        return "grant"
    if any(w in text for w in ("startup", "accelerator", "incubator", "venture", "pitch")):
        return "startup"
    return "job"
```

This single change will correctly label the ~20 grant/funding results
currently mislabeled as "job" on every future discovery run.

#### Step 1.2: Add title-level dedup to orchestrator.py

After URL dedup, add normalized title dedup:

```python
def _normalize_title(title: str) -> str:
    import re
    t = title.lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t[:100]

# In run_all(), maintain a set of normalized titles per run:
normalized_seen: set[str] = set()
# Before adding:
norm = _normalize_title(opp.title)
if norm in normalized_seen:
    continue
normalized_seen.add(norm)
```

#### Step 1.3: Create repair_data.py script

A one-time script that:

1. **Repair categories**: Update google_search records where title contains
   grant/funding/scholarship keywords → set category to "grant"

2. **Deduplicate**: For duplicate titles, keep the record with the most recent
   created_at, archive the others (set status="dead")

3. **Clean twitter URLs**: Mark twitter entries with non-twitter URLs or
   generic search URLs as status="dead"

4. **Backfill scores**: Set defaults for new columns

```python
# scripts/repair_data.py — overview
def repair_categories(session):
    session.execute("""
        UPDATE opportunities
        SET category = 'grant'
        WHERE source = 'google_search'
          AND category = 'job'
          AND (LOWER(title) LIKE '%grant%'
               OR LOWER(title) LIKE '%funding%'
               OR LOWER(title) LIKE '%fellowship%')
    """)

def deduplicate_by_title(session):
    # Find duplicate normalized titles
    # Keep newest, mark rest as dead
    ...

def clean_twitter(session):
    # Mark non-twitter URLs as dead
    ...
```

#### Step 1.4: Fix twitter.py URL generation

Twitter scraper uses `site:twitter.com` queries on Serper, which returns
linkedIn URLs, random pages, etc. Add validation:

```python
# Before appending to results:
if not any(domain in link.lower() for domain in ("twitter.com", "x.com")):
    continue  # Skip non-twitter results
```

### Testing
- Run repair script against a copy of production DB first
- Verify category counts shift from 328→~308 job, ~20 grant
- Verify duplicate title groups reduced
- Run google_search with mock Serper response, verify category labels

### Deployment
- Run `scripts/repair_data.py` on VPS inside docker container
- Requires prod DB backup first
- Copy `data/job_bot.db` to `data/job_bot.db.bak` before running

### Estimated Effort: 1 day

---

## Phase 2: ATS Discovery Providers

**Goal**: Add direct JSON API scrapers for Greenhouse, Lever, and Ashby
ATS platforms, reducing reliance on costly Serper API calls.

### Dependencies
- Phase 0 — needs `sources.yaml` and `ProviderConfig` model

### Files to Create
- `job_bot/discovery/providers/__init__.py`
- `job_bot/discovery/providers/greenhouse.py`
- `job_bot/discovery/providers/lever.py`
- `job_bot/discovery/providers/ashby.py`
- `job_bot/discovery/providers/base.py`

### Files to Modify
- `job_bot/discovery/__init__.py` — Import new providers
- `job_bot/discovery/orchestrator.py` — Integrate ATS provider execution
- `job_bot/discovery/registry.py` — Allow non-scraper providers if needed
- `data/sources.yaml` — Add ATS company targets

### Implementation Steps

#### Step 2.1: Create providers/base.py

```python
# job_bot/discovery/providers/base.py

from abc import ABC, abstractmethod
from job_bot.discovery.base import Opportunity

class ATSProvider(ABC):
    """Base class for ATS-specific job API scrapers."""
    name: str = ""

    @abstractmethod
    async def fetch_jobs(self, companies: list[str]) -> list[Opportunity]:
        ...

    @abstractmethod
    async def check_live(self, url: str) -> bool:
        """Check if a specific posting is still accepting applications."""
        ...
```

#### Step 2.2: Create providers/greenhouse.py

Greenhouse has a public JSON API:
`GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs`
`GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{id}`

```python
# job_bot/discovery/providers/greenhouse.py

import httpx
from .base import ATSProvider
from job_bot.discovery.base import Opportunity

GREENHOUSE_BOARDS = {
    "openai": "openai",
    "stripe": "stripe",
    "airbnb": "airbnb",
    "gitlab": "gitlab",
    "notion": "notion",
    "vercel": "vercel",
    "datadog": "datadog",
    "hashicorp": "hashicorp",
}

class GreenhouseProvider(ATSProvider):
    name = "greenhouse"

    def __init__(self, companies: list[str] | None = None):
        self.companies = companies or list(GREENHOUSE_BOARDS.keys())

    async def fetch_jobs(self, companies: list[str] | None = None) -> list[Opportunity]:
        targets = companies or self.companies
        results = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for company in targets:
                board = GREENHOUSE_BOARDS.get(company, company)
                try:
                    resp = await client.get(
                        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                        params={"content": "true", "per_page": 100},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for job in data.get("jobs", []):
                        results.append(Opportunity(
                            title=job.get("title", ""),
                            company=company,
                            url=job.get("absolute_url", ""),
                            description=job.get("content", ""),
                            source="greenhouse_ats",
                            category="job",
                        ))
                except Exception:
                    continue
        return results

    async def check_live(self, url: str) -> bool:
        # Parse board token and job ID from URL
        # https://boards.greenhouse.io/{board}/jobs/{job_id}
        import re
        m = re.match(r"https://boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
        if not m:
            return False
        board, job_id = m.group(1), m.group(2)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
                )
                return resp.status_code == 200
            except Exception:
                return False
```

#### Step 2.3: Create providers/lever.py

Lever API:
`GET https://api.lever.co/v0/postings/{company}?limit=100` (public, no auth)

```python
# job_bot/discovery/providers/lever.py

LEVER_COMPANIES = [
    "stripe", "notion", "linear", "calendly", "deel",
    "brex", "canva", "webflow", "discord",
]
```

#### Step 2.4: Create providers/ashby.py

Ashby API:
`POST https://api.ashbyhq.com/posting-api/job-board/{company}`
with `{"boardIdentifier": company}` — returns structured job listings.

#### Step 2.5: Integrate into orchestrator.py

In `run_all()`, after iterating scrapers, also run ATS providers:

```python
# In DiscoveryOrchestrator.run_all():
from job_bot.discovery.providers.greenhouse import GreenhouseProvider
from job_bot.discovery.providers.lever import LeverProvider
from job_bot.discovery.providers.ashby import AshbyProvider

ats_providers = [
    GreenhouseProvider(),
    LeverProvider(),
    AshbyProvider(),
]
for provider in ats_providers:
    try:
        opps = await provider.fetch_jobs()
        for opp in opps:
            oid = self.repo.add_opportunity({...})
            if oid:
                all_ops.append(opp)
    except Exception as e:
        logger.error("ats_provider_failed", provider=provider.name, error=str(e))
```

### Testing
- Mock httpx responses for each ATS API
- Verify parsed Opportunity objects have correct fields
- Test `check_live()` with live and dead URLs
- Test with real API calls (manual, no credentials needed — these are public APIs)

### Deployment
- No new dependencies — uses httpx (already installed)
- Docker rebuild recommended but not strictly required
- Update `sources.yaml` with ATS companies list

### Estimated Effort: 2 days

---

## Phase 3: Liveness Check

**Goal**: Before spending LLM tokens on scoring, verify the posting is
still accepting applications. Two-rung approach: ATS API → HTTP check →
content classifier.

### Dependencies
- Phase 2 — ATS providers implement `check_live()`

### Files to Create
- `job_bot/intelligence/liveness.py` — Liveness checker

### Files to Modify
- `job_bot/review/manager.py` — Add liveness check before scoring
- `job_bot/pipeline.py` — Wire liveness checker
- `job_bot/database/repository.py` — Add liveness update methods
- `job_bot/dashboard/server.py` — Show liveness status in review UI

### Implementation Steps

#### Step 3.1: Create intelligence/liveness.py

```python
# job_bot/intelligence/liveness.py

import httpx
import re
from bs4 import BeautifulSoup
from job_bot.discovery.providers.greenhouse import GreenhouseProvider
from job_bot.discovery.providers.lever import LeverProvider
from job_bot.discovery.providers.ashby import AshbyProvider
from job_bot.utils.logging import get_logger

logger = get_logger()

# Provider registry keyed by URL pattern
LIVENESS_PROVIDERS = [
    (re.compile(r"boards\.greenhouse\.io/.*/jobs/\d+"), GreenhouseProvider()),
    (re.compile(r"jobs\.lever\.co/[^/]+/[^/]+"), LeverProvider()),
    (re.compile(r"jobs\.ashbyhq\.com/[^/]+"), AshbyProvider()),
]


class LivenessChecker:
    def __init__(self):
        self._http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

    async def check(self, url: str) -> tuple[bool, str]:
        """Returns (is_live, source) where source is which check caught it."""
        # Rung 1: ATS-specific API check
        for pattern, provider in LIVENESS_PROVIDERS:
            if pattern.search(url):
                is_live = await provider.check_live(url)
                return is_live, "ats_api"

        # Rung 2: HTTP status check + content sniffing
        try:
            resp = await self._http_client.get(url)
            if resp.status_code == 404 or resp.status_code == 410:
                return False, "http_status"
            if resp.status_code == 200:
                # Rung 3: Content classifier — check for "no longer accepting"
                soup = BeautifulSoup(resp.text, "html.parser")
                text = soup.get_text(separator=" ", strip=True)[:2000].lower()
                dead_phrases = [
                    "no longer accepting", "position has been filled",
                    "this posting is no longer", "job has been removed",
                    "page not found", "this job is no longer",
                ]
                if any(p in text for p in dead_phrases):
                    return False, "content_classifier"
                return True, "http_ok"
        except Exception:
            pass
        return True, "unknown"  # Assume live if we can't determine
```

#### Step 3.2: Update review/manager.py

Add liveness check before scoring:

```python
# In _review_one():
# New first step:
from job_bot.intelligence.liveness import LivenessChecker
checker = LivenessChecker()
is_live, live_source = await checker.check(opp.url)
# Update opp liveness status in DB
self.repo.update_opportunity_liveness(opp.id, "live" if is_live else "dead", live_source)
if not is_live:
    self.repo.update_opportunity_status(opp.id, "dead")
    logger.info("skipping_dead_posting", opp_id=opp.id, url=opp.url)
    return None  # Skip scoring
# ... existing scoring logic ...
```

### Testing
- Test with known Greenhouse/Lever/Ashby URLs (both live and dead)
- Test HTTP fallback with 404, 410, 200 responses
- Test content classifier with dead-phrase detection
- Test that dead postings are not scored

### Deployment
- Requires `beautifulsoup4` (already installed)
- No Docker rebuild needed for pure Python changes

### Estimated Effort: 1 day

---

## Phase 4: Multi-Dim Scoring

**Goal**: Replace single 0-100 score with 6-dimensional prose scoring that
gives richer signal for the review queue.

### Dependencies
- Phase 0 — needs new score columns in models.py

### Files to Modify
- `job_bot/intelligence/matcher.py` — New scoring prompt and parsing
- `job_bot/review/manager.py` — Handle multi-dim scores
- `job_bot/database/repository.py` — Store multi-dim scores
- `job_bot/dashboard/server.py` — Expose multi-dim scores in API
- `job_bot/dashboard/templates/review.html` — Display radar chart
- `job_bot/dashboard/templates/opportunities.html` — Show score breakdown

### Implementation Steps

#### Step 4.1: Rewrite matcher.py scoring

Replace the single prompt with a structured prompt that returns 6 scores:

```python
# job_bot/intelligence/matcher.py — new score() method

SCORING_PROMPT = """Rate this opportunity across 6 dimensions.
Return ONLY valid JSON with these keys (no markdown, no explanation):

{{
  "cv_match": <0-100 how well does the profile match the requirements>,
  "compensation": <0-100 how competitive is the pay/benefits>,
  "culture": <0-100 how well does the company culture fit>,
  "red_flags": <0-100 how many red flags (inverted: 0=many flags, 100=clean)>,
  "legitimacy": <0-100 how legitimate/verifiable is this opportunity>,
  "global": <0-100 how accessible is this for global applicants>,
  "prose": "<2-3 sentence summary of why or why not>"
}}

PROFILE:
{profile}

OPPORTUNITY:
{opportunity}
"""

async def score(self, profile_text: str, opportunity_text: str, category: str = "job") -> dict:
    prompt = SCORING_PROMPT.format(
        profile=profile_text[:2000],
        opportunity=opportunity_text[:2000],
    )
    result = await self.provider.generate(prompt, system="You are a career opportunity evaluator. Return JSON only.")
    try:
        import json
        scores = json.loads(result.strip())
        # Validate all keys present
        required = {"cv_match", "compensation", "culture", "red_flags", "legitimacy", "global", "prose"}
        if not required.issubset(scores.keys()):
            raise ValueError(f"Missing keys: {required - scores.keys()}")
        # Clamp values
        for k in required - {"prose"}:
            scores[k] = max(0, min(100, int(scores[k])))
        scores["composite"] = sum(scores[k] for k in required - {"prose"}) // 6
        return scores
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("score_parse_failed", error=str(e), raw=result[:200])
        return {
            "cv_match": 50, "compensation": 50, "culture": 50,
            "red_flags": 50, "legitimacy": 50, "global": 50,
            "prose": "Score parsing failed. Manual review recommended.",
            "composite": 50,
        }
```

#### Step 4.2: Update review/manager.py

```python
# In _review_one(), replace:
# score = await self.matcher.score(...)
# With:
scores = await self.matcher.score(
    profile.get("cv_text", ""),
    f"{opp.title} {opp.description}",
    category=opp.category,
)
# Store scores
self.repo.update_opportunity_scores(opp.id, scores)
# Use composite for sorting
composite_score = scores["composite"] / 100.0  # Normalize to 0-1 for backward compat
```

#### Step 4.3: Add update_opportunity_scores to repository.py

```python
def update_opportunity_scores(self, opp_id: int, scores: dict) -> bool:
    with Session(self.engine) as session:
        record = session.query(Opportunity).filter_by(id=opp_id).first()
        if not record:
            return False
        record.score = scores.get("composite", 50) / 100.0
        record.score_cv_match = scores.get("cv_match")
        record.score_compensation = scores.get("compensation")
        record.score_culture = scores.get("culture")
        record.score_red_flags = scores.get("red_flags")
        record.score_legitimacy = scores.get("legitimacy")
        record.score_global = scores.get("global")
        record.score_prose = scores.get("prose")
        session.commit()
        return True
```

#### Step 4.4: Update review.html template

Add a simple bar visualization for the 6 dimensions:

```javascript
// In review.html, after score display:
function renderScoreBars(oppId, scores) {
    const container = document.getElementById('scores-' + oppId);
    const dims = ['cv_match', 'compensation', 'culture', 'red_flags', 'legitimacy', 'global'];
    const labels = {'cv_match': 'CV Match', 'compensation': 'Comp', 'culture': 'Culture',
                    'red_flags': 'Flags', 'legitimacy': 'Legit', 'global': 'Global'};
    let html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin: 8px 0;">';
    dims.forEach(d => {
        const val = scores[d] || 0;
        const color = val >= 70 ? '#2e7d32' : val >= 40 ? '#f57f17' : '#c62828';
        html += `<div style="font-size: 0.75rem;"><span>${labels[d]}</span>
                 <div style="background: #eee; height: 8px; border-radius: 4px; margin-top: 2px;">
                 <div style="background: ${color}; width: ${val}%; height: 8px; border-radius: 4px;"></div></div></div>`;
    });
    html += '</div>';
    if (scores.prose) html += `<p style="font-size: 0.8rem; color: #666;">${scores.prose}</p>`;
    container.innerHTML = html;
}
```

### Testing
- Test JSON parsing from LLM response
- Test fallback when LLM returns invalid JSON
- Test score storage and retrieval
- Test frontend rendering with sample data

### Deployment
- Run migration to add new columns (or create fresh DB)
- Docker rebuild not required (pure Python + template changes)

### Estimated Effort: 2 days

---

## Phase 5: Batch Review + Dashboard Improvements

**Goal**: Improve the review queue with sorting by composite score,
batch operations, and filtering by liveness status.

### Dependencies
- Phase 3 — needs liveness data
- Phase 4 — needs multi-dim scores

### Files to Modify
- `job_bot/dashboard/server.py` — Sort review queue, expose score breakdown
- `job_bot/dashboard/templates/review.html` — Better layout, batch actions
- `job_bot/dashboard/templates/home.html` — Show scored vs unscored counts
- `job_bot/database/repository.py` — New query methods for sorted/filtered
- `job_bot/review/manager.py` — Concurrent batch processing

### Implementation Steps

#### Step 5.1: Sorted review queue in repository.py

```python
def get_pending_opportunities_sorted(
    self, min_score: float = 0.0, category: str | None = None,
    limit: int = 50, sort_by: str = "score_desc",
) -> list:
    with Session(self.engine) as session:
        query = session.query(Opportunity).filter(
            Opportunity.status == "new",
            Opportunity.liveness_status != "dead",  # Skip dead
        )
        if category:
            query = query.filter(Opportunity.category == category)
        if min_score > 0:
            query = query.filter(
                Opportunity.score.is_(None) | (Opportunity.score >= min_score)
            )
        if sort_by == "score_desc":
            query = query.order_by(Opportunity.score.desc().nullslast())
        elif sort_by == "created_desc":
            query = query.order_by(Opportunity.created_at.desc())
        return query.limit(limit).all()
```

#### Step 5.2: Update dashboard review endpoint

```python
# In server.py, update /review endpoint
@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request, category: str = "all", sort: str = "score_desc"):
    repo = get_repo()
    pending = repo.get_pending_opportunities_sorted(
        min_score=0.3, category=category if category != "all" else None,
        sort_by=sort,
    )
    # ... render with scores ...
```

#### Step 5.3: Update review.html template

- Add sort dropdown (Score, Date, Category)
- Show score breakdown bars (from Phase 4)
- Add "Skip" action (marks as evaluated without applying)
- Liveness indicator badge ("Live" / "Dead" / "Unknown")

#### Step 5.4: Concurrent batch processing in review/manager.py

Already uses `asyncio.gather` with semaphore. Add:

```python
async def review_batch(self, profile: dict, limit: int = 10) -> list:
    pending = self.repo.get_pending_opportunities_sorted(limit=limit)
    tasks = [self._review_one(opp, profile) for opp in pending]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]  # Filter dead/skipped
```

#### Step 5.5: Home dashboard stats

Add to home page:
- "Scored" vs "Unscored" count
- Live vs Dead count
- Simple funnel: Discovered → Live → Scored → Applied

### Testing
- Test sorting by composite score
- Test filtering by liveness status
- Test batch review processes specified number
- Verify dashboard stats match reality

### Deployment
- Template changes only, no Docker rebuild

### Estimated Effort: 1 day

---

## Phase 6: Comprehensive Tests

**Goal**: Build a proper test suite covering all major components.

### Dependencies
- All previous phases

### Files to Create
- `tests/test_liveness.py` — Liveness checker tests
- `tests/test_providers/` — ATS provider tests
  - `tests/test_providers/__init__.py`
  - `tests/test_providers/test_greenhouse.py`
  - `tests/test_providers/test_lever.py`
  - `tests/test_providers/test_ashby.py`
- `tests/test_scoring.py` — Multi-dim scoring tests
- `tests/test_sources.py` — Sources config tests
- `tests/conftest.py` — Shared fixtures

### Files to Modify
- `tests/test_discovery.py` — Add provider tests, sources tests
- `tests/test_database.py` — Add new model field tests

### Implementation Strategy

#### Step 6.1: Create conftest.py with shared fixtures

```python
# tests/conftest.py
import pytest
import tempfile
from job_bot.database.repository import init_db, Repository
from job_bot.database.models import Base, Opportunity

@pytest.fixture
def db():
    """In-memory SQLite database for tests."""
    db_url = init_db(":memory:")
    return Repository(db_url)

@pytest.fixture
def sample_opportunity():
    return {
        "title": "Software Engineer",
        "company": "Test Corp",
        "url": "https://example.com/job/123",
        "description": "A test job posting",
        "source": "test",
        "category": "job",
    }
```

#### Step 6.2: Mock strategy for external services

Create mock httpx client fixtures:

```python
# tests/test_providers/test_greenhouse.py
import pytest
from httpx import Response
from job_bot.discovery.providers.greenhouse import GreenhouseProvider

GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "title": "Software Engineer",
            "absolute_url": "https://boards.greenhouse.io/test/jobs/123",
            "content": "<p>Job description here</p>",
        }
    ]
}

@pytest.mark.asyncio
async def test_greenhouse_fetch_jobs(httpx_mock):
    httpx_mock.add_response(
        url="https://boards-api.greenhouse.io/v1/boards/test/jobs",
        json=GREENHOUSE_RESPONSE,
    )
    provider = GreenhouseProvider(companies=["test"])
    jobs = await provider.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].title == "Software Engineer"
    assert jobs[0].company == "test"
```

#### Step 6.3: Multi-dim scoring tests

```python
# tests/test_scoring.py
import pytest
from job_bot.intelligence.matcher import Matcher

class MockProvider:
    def __init__(self, response: str):
        self._response = response
    async def generate(self, prompt: str, system: str | None = None) -> str:
        return self._response

class TestMultiDimScoring:
    @pytest.mark.asyncio
    async def test_valid_json_response(self):
        mock = MockProvider('{"cv_match": 85, "compensation": 60, "culture": 70, "red_flags": 90, "legitimacy": 80, "global": 75, "prose": "Good fit"}')
        matcher = Matcher(mock)
        scores = await matcher.score("Profile", "Job posting")
        assert scores["cv_match"] == 85
        assert scores["composite"] == 76  # (85+60+70+90+80+75)//6

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        mock = MockProvider("not json at all")
        matcher = Matcher(mock)
        scores = await matcher.score("Profile", "Job")
        assert scores["composite"] == 50  # Fallback value
```

#### Step 6.4: Liveness tests

```python
# tests/test_liveness.py
@pytest.mark.asyncio
async def test_greenhouse_live_url(httpx_mock):
    httpx_mock.add_response(
        url="https://boards-api.greenhouse.io/v1/boards/test/jobs/123",
        json={"id": 123, "title": "Engineer"},
    )
    checker = LivenessChecker()
    is_live, source = await checker.check("https://boards.greenhouse.io/test/jobs/123")
    assert is_live is True
    assert source == "ats_api"

@pytest.mark.asyncio
async def test_404_detection(httpx_mock):
    httpx_mock.add_response(status_code=404)
    checker = LivenessChecker()
    is_live, source = await checker.check("https://example.com/dead-job")
    assert is_live is False
    assert source == "http_status"
```

### Testing
- Run: `pytest tests/ -v --cov=job_bot`
- Target: >70% coverage for new code
- All existing tests must still pass

### Deployment
- No Docker impact — tests run locally or in CI only

### Estimated Effort: 1 day

---

## Data Model Changes Summary

### New columns on `Opportunity` table (Phase 0 + 4)

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `status` | String(50) | "new" | Already exists, now using canonical values |
| `liveness_checked_at` | DateTime | NULL | When liveness was last checked |
| `liveness_status` | String(20) | NULL | "live", "dead", "unknown" |
| `score_cv_match` | Float | NULL | CV fit dimension |
| `score_compensation` | Float | NULL | Compensation dimension |
| `score_culture` | Float | NULL | Culture fit dimension |
| `score_legitimacy` | Float | NULL | Legitimacy dimension |
| `score_red_flags` | Float | NULL | Red flags dimension |
| `score_global` | Float | NULL | Global accessibility dimension |
| `score_prose` | Text | NULL | Prose summary of evaluation |

### Migration Strategy

SQLite ALTER TABLE only supports ADD COLUMN (not DROP or MODIFY).
Since we're only adding columns, this is safe:

```sql
ALTER TABLE opportunities ADD COLUMN liveness_checked_at DATETIME;
ALTER TABLE opportunities ADD COLUMN liveness_status VARCHAR(20) DEFAULT NULL;
ALTER TABLE opportunities ADD COLUMN score_cv_match FLOAT;
ALTER TABLE opportunities ADD COLUMN score_compensation FLOAT;
ALTER TABLE opportunities ADD COLUMN score_culture FLOAT;
ALTER TABLE opportunities ADD COLUMN score_legitimacy FLOAT;
ALTER TABLE opportunities ADD COLUMN score_red_flags FLOAT;
ALTER TABLE opportunities ADD COLUMN score_global FLOAT;
ALTER TABLE opportunities ADD COLUMN score_prose TEXT;
```

Run via `scripts/repair_data.py` or separate migration script.

---

## Configuration Changes

### New config keys in `config_default.yaml`

```yaml
discovery:
  # ... existing keys ...
  sources_path: "data/sources.yaml"  # NEW
  liveness_check: true  # NEW - enable/disable liveness checking
```

### New file: `data/sources.yaml`

```yaml
# Central declarative source configuration
providers:
  ats_greenhouse:
    enabled: true
    type: ats_direct
    companies:
      - openai
      - stripe
      - gitlab
      - vercel

  ats_lever:
    enabled: true
    type: ats_direct
    companies:
      - stripe
      - linear
      - notion

  ats_ashby:
    enabled: true
    type: ats_direct
    companies: []

  serper_google:
    enabled: true
    type: serper
    queries:
      - "{skill} 1099 contract remote 2026"
      - "{skill} freelance remote"

  company_targets:
    enabled: true
    type: html
    companies:
      - remote4africa.com
      - remoteok.com
      - weworkremotely.com
```

### Backward Compatibility

- Old config keys still work (sources dict, serper_api_key, etc.)
- `sources.yaml` is optional — if missing, use hardcoded defaults
- New `sources.yaml` replaces hardcoded queries in individual scrapers when present

---

## Testing Strategy

### Test File Matrix

| Test File | What It Tests | Mock Strategy |
|-----------|--------------|---------------|
| `tests/test_discovery.py` | Existing scraper registry + basic ops | In-memory DB |
| `tests/test_database.py` | New model fields, migration | In-memory SQLite |
| `tests/test_intelligence.py` | Existing + multi-dim scoring | Mock LLM provider |
| `tests/test_liveness.py` | Liveness checker | httpx_mock |
| `tests/test_providers/test_greenhouse.py` | Greenhouse ATS API | httpx_mock |
| `tests/test_providers/test_lever.py` | Lever ATS API | httpx_mock |
| `tests/test_providers/test_ashby.py` | Ashby ATS API | httpx_mock |
| `tests/test_scoring.py` | Multi-dim scoring + fallback | Mock LLM provider |
| `tests/test_config.py` | Updated config parsing | File fixtures |
| `tests/test_sources.py` | Sources.yaml loading | File fixtures |
| `tests/test_review.py` | Review manager with liveness | In-memory DB + mocks |

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=job_bot --cov-report=term-missing

# Run specific test file
pytest tests/test_scoring.py -v
```

### CI/CD (GitHub Actions)

After Phase 6, add `.github/workflows/test.yml`:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --cov=job_bot
```

---

## Ordering Rationale

### Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

**Why this order:**

1. **Phase 0 first** — Everything depends on the data model. Canonical statuses
   and new score columns must exist before any code writes to them.

2. **Phase 1 second** — Fix the existing 607 records before adding new features.
   This is the cheapest way to improve the system immediately (just a script + small
   scraper changes). Also validates that Phase 0 migrations work correctly on prod data.

3. **Phase 2 third** — ATS providers reduce Serper API costs and give us direct,
   structured data. This is the highest-ROI new feature. Must come before liveness
   check (Phase 3) because liveness leverages ATS provider APIs.

4. **Phase 3 fourth** — Liveness check prevents wasting LLM tokens on dead postings.
   Directly reduces cost. Needs ATS providers for the first rung.

5. **Phase 4 fifth** — Multi-dim scoring is the most sophisticated change.
   Depends on new score columns (Phase 0) and liveness (Phase 3) to avoid
   scoring dead postings.

6. **Phase 5 sixth** — Dashboard improvements depend on all the data flowing
   from previous phases. Sorting by composite score, filtering by liveness.

7. **Phase 6 last** — Tests are most valuable once the system is stable.
   Writing tests for code that's still changing creates maintenance burden.

### Parallelization Opportunities

| Work Stream | Can Parallelize With | Why |
|-------------|---------------------|-----|
| Phase 0 model changes | Phase 6 test infrastructure | Tests don't depend on live data |
| Phase 1 repair script | Phase 2 ATS provider research | Independent work |
| Phase 2 ATS providers | Phase 0 config + sources design | Just need to agree on interfaces |
| Phase 6 individual test files | Each other | No cross-dependencies |

### Risk Points

1. **LLM JSON parsing** (Phase 4) — The model must return valid JSON.
   Mitigation: robust fallback to default values, prompt engineering.

2. **ATS API rate limits** (Phase 2) — Public APIs may throttle.
   Mitigation: add delay between requests, respect retry-after headers.

3. **SQLite concurrency** — Multiple async workers writing to SQLite.
   Mitigation: WAL mode (`PRAGMA journal_mode=WAL`), single writer pattern.

4. **Disk space** (88% used) — Data migrations create backup copies.
   Mitigation: compress old data, run repair script conservatively.

---

## Effort Summary

| Phase | Description | Days | Deployable |
|-------|-------------|------|------------|
| 0 | Foundation | 2 | Yes (config + migration) |
| 1 | Fix Existing Data | 1 | Yes (script) |
| 2 | ATS Discovery | 2 | Yes (code only) |
| 3 | Liveness Check | 1 | Yes (code only) |
| 4 | Multi-Dim Scoring | 2 | Yes (code + migration) |
| 5 | Dashboard Improvements | 1 | Yes (templates) |
| 6 | Comprehensive Tests | 1 | Yes (CI config) |
| **Total** | | **10 days** | |

Each phase is independently deployable to the VPS. Ordering follows the
dependency chain — no phase requires a later phase to be complete.
