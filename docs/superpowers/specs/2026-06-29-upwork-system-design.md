# Upwork System — Phase 1 Design

**Date:** 2026-06-29
**Status:** Draft
**Scope:** Phase 1 — Scraper + Dashboard (no email)

## Overview

A dedicated Upwork integration within JBot that scrapes Upwork job listings via RSS feeds, extracts client company information from job detail pages, and presents everything in a new "Upwork" dashboard section. Email outreach is deferred to Phase 2.

## Architecture

```
Upwork RSS Feed (httpx)
       ↓
RSS Parser (BS4 / XML) → Opportunity objects
       ↓
crawl4ai (headless) → Job detail page → Extract client company name + website
       ↓
Store in DB (source="upwork")
       ↓
Dashboard: Upwork page → Table of jobs with client info
```

## Components

### 1. Upwork Scraper (`job_bot/discovery/upwork.py`)

**Pattern:** `@register("upwork")` + `BaseScraper` (same as Fuzu, african_jobs).

**RSS Feed URL:**
```
https://www.upwork.com/ab/feed/topics/rss?q={keywords}&paging=0%3B20
```
- `{keywords}` — URL-encoded keywords from user config
- `paging=0%3B20` — first 20 results
- No authentication needed

**RSS Parsing (BS4):**
```python
soup = BeautifulSoup(resp.text, "xml")   # or "html.parser"
for item in soup.find_all("item"):
    title = item.find("title").text
    link = item.find("link").text
    desc = item.find("description").text
    pubDate = item.find("pubDate").text
```

RSS gives: title, url, description (HTML with skills, budget, country, type), pubDate.
RSS does NOT give: client company name, client website.

**Client Info Enrichment (crawl4ai):**
For each job, visit the job detail page via crawl4ai (headless Chromium):
```python
content, error = await self._crawler.enrich(job_url)
soup = BeautifulSoup(content, "html.parser")
# Extract from structured sections on the page
```
Target data: client company name, client website URL, client location.

**Fallback:** If crawl4ai fails, use httpx+BS4 fallback (may get partial data from server-rendered content).

**Scraper Flow:**
1. Fetch RSS by user keywords
2. Parse items into `Opportunity` with `source="upwork"`
3. For each opportunity, call crawl4ai to enrich client info
4. Store client company + website on the opportunity
5. Dedup by URL

### 2. Config (`job_bot/config.py`)

Add a new config section:

```python
class UpworkConfig(BaseModel):
    enabled: bool = True
    keywords: list[str] = Field(default_factory=lambda: ["Python", "AI", "Data Science"])
    max_jobs_per_run: int = 20
    email_service: str = ""       # Phase 2: "sendgrid" or "mailgun"
    email_api_key: str = ""       # Phase 2
    from_email: str = ""           # Phase 2
```

Add to `Config`:
```python
upwork: UpworkConfig = Field(default_factory=UpworkConfig)
```

The `keywords` field is editable from the dashboard Upwork settings page.

Add `"upwork": True` to `DiscoveryConfig.sources` defaults.

### 3. Database (`job_bot/database/models.py`)

Add columns to `Opportunity` table for client data:

```python
client_company = Column(String(300), default="")   # Client company name
client_website = Column(String(2000), default="")  # Client website URL
```

These are nullable/empty by default. Only populated when crawl4ai successfully extracts from job detail page.

Run schema migration in `repository.py:migrate_schema()` — safe to add new columns to existing table.

### 4. Dashboard

**New sidebar menu item** in `base.html`:
```html
<li>
    <a href="/upwork" class="{{ 'active' if page == 'upwork' }}">🟢 Upwork</a>
    {% if page == 'upwork' %}
    <ul style="padding-left: 1.5rem; list-style: none;">
        <li><a href="/upwork/jobs" style="font-size: 0.85rem;">📌 Jobs</a></li>
        <li><a href="/upwork/settings" style="font-size: 0.85rem;">⚙️ Settings</a></li>
    </ul>
    {% endif %}
</li>
```

**New routes in `server.py`:**

| Route | Template | Description |
|---|---|---|
| `/upwork` | `upwork.html` | Main Upwork page (redirects to `/upwork/jobs`) |
| `/upwork/jobs` | `upwork_jobs.html` | Table of Upwork jobs with client info |
| `/upwork/settings` | `upwork_settings.html` | Keyword input, run discovery button |

**Upwork Jobs page (`upwork_jobs.html`):**
- Table columns: Title, Client Company, Website URL, Budget/Skills (from description), Posted, Status, Actions
- Filterable by status (new/contacted/ignored)
- Sorted by most recent
- Each row shows the Upwork job title, detected client company, and company website

**Upwork Settings page (`upwork_settings.html`):**
- Text input for interest keywords (comma-separated)
- "Run Upwork Discovery" button (POST to `/api/upwork/discover`)
- Save keywords button

### 5. Discovery Flow

When triggered (from dashboard or cron):
1. Orchestrator calls `upwork` scraper (if enabled in sources)
2. Scraper fetches RSS by keywords, parses jobs
3. For each new job (not in DB), scrape detail page for client info
4. Store all opportunities with `source="upwork"`
5. Return count of new entries

The existing orchestrator in `orchestrator.py` already iterates all registered scrapers. The Upwork scraper fits into this loop.

### Files to Create

| File | Purpose |
|---|---|
| `job_bot/discovery/upwork.py` | Upwork scraper (RSS + crawl4ai enrichment) |
| `job_bot/dashboard/templates/upwork.html` | Upwork main page (redirect) |
| `job_bot/dashboard/templates/upwork_jobs.html` | Jobs table with client info |
| `job_bot/dashboard/templates/upwork_settings.html` | Keywords + discovery trigger |

### Files to Modify

| File | Change |
|---|---|
| `job_bot/discovery/__init__.py` | Add `from job_bot.discovery import upwork` |
| `job_bot/config.py` | Add `UpworkConfig` class + `upwork` field on `Config` |
| `job_bot/database/models.py` | Add `client_company`, `client_website` columns to `Opportunity` |
| `job_bot/database/repository.py` | Add new columns to `migrate_schema()` |
| `job_bot/dashboard/templates/base.html` | Add "Upwork" nav item |
| `job_bot/dashboard/server.py` | Add upwork routes + API endpoints |
| `job_bot/dashboard/templates/settings.html` | Already done (model dropdown) |

### Excluded (Phase 2)

- Email sending (SendGrid/Mailgun integration)
- `email_log` table for tracking
- Email status tracking (sent/opened/replied)
- Auto-generated cover letters for Upwork proposals
- Company contact email enrichment

### Open Questions

1. crawl4ai stability: The headless Chromium on the server had issues earlier (`BrowserType.launch` error). May need to debug this before the Upwork scraper can enrich client info. Fallback: httpx-only (client info may be empty for some jobs).
2. Upwork RSS feed rate limits: Unknown. We're scraping at most 20 jobs per run, once per discovery cycle (24h default). Should be fine.

### Risks

| Risk | Mitigation |
|---|---|
| Upwork blocks RSS | RSS is public, no auth. Low risk. |
| crawl4ai unstable | httpx fallback, partial data |
| Client info not available on job page | Some jobs show client, some don't. Partial data is acceptable. |
| Server network down | Can't scrape. Retry on next cycle. |
