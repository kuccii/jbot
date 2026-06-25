# Opportunity Categories: Jobs, Startups & Grants

**Date:** 2026-06-25
**Status:** Draft
**Designer:** Patrick Hirwa / JBot team

## Problem

JBot discovers three fundamentally different types of opportunities — jobs (1099/contractor roles), startup programs (Y Combinator, accelerators), and grants/fellowships — but treats them all as a single "Opportunity" entity. This means:
- A user browsing job listings also sees grant deadlines and accelerator calls mixed in
- The application flow is the same (cover letter) when startups need pitch summaries and grants need proposals
- Scoring criteria don't match: jobs need skill-match scoring, startups need program-prestige scoring
- UI columns are generic (company, location) and miss startup-specific fields (program, stage, amount)

## Design

### 1. Data Model

Add to the existing `Opportunity` table in `job_bot/database/models.py`:

| Column | Type | Default | Description |
|---|---|---|---|
| `category` | `String(50)` | `"job"` | One of: `"job"`, `"startup"`, `"grant"` |
| `program` | `String(300)` | `""` | Program name (e.g. "YC W26", "Techstars") |
| `stage` | `String(100)` | `""` | Stage (e.g. "Pre-seed", "Seed") |
| `amount` | `String(200)` | `""` | Funding amount offered (e.g. "$500K", "$20K grant") |

Existing fields already cover job-specific needs: `location`, `salary_range`, `remote`, `deadline`.

**Migration:** Existing rows get category inferred from `source` column:
- `google_search`, `linkedin`, `company_pages` → `"job"`
- `grants` → `"grant"`
- `ycombinator` → `"startup"`
- Unknown → `"job"`

### 2. Scrapers & Discovery

The `Opportunity` dataclass in `job_bot/discovery/base.py` gets new fields:
- `category` (str, default "job")
- `program` (str, default "")
- `stage` (str, default "")
- `amount` (str, default "")

Each scraper tags its output:

| Scraper | Category | Notes |
|---|---|---|
| `google_search` | `job` | Searches for 1099/contract remote jobs |
| `linkedin` | `job` | Contract/freelance positions |
| `company_pages` | `job` | Career page listings |
| `grants` | `grant` | Grants & fellowships |
| `ycombinator` | `startup` | YC jobs board / startup roles (or new dedicated startup scraper) |

The orchestrator passes category through to the repository when saving.

### 3. Repository

- `get_pending_opportunities()` gets an optional `category` filter parameter
- New method: `get_stats_by_category()` for per-category counts
- The existing `get_stats()` remains but can be extended to break down by category

### 4. Scoring (Matcher)

Strategy pattern per category:

```python
class BaseScorer(ABC):
    async def score(self, cv_text: str, opp_text: str) -> float: ...

class JobScorer(BaseScorer): ...
class StartupScorer(BaseScorer): ...
class GrantScorer(BaseScorer): ...
```

- **JobScorer** — skill match + remote-friendliness (existing logic from Matcher, unchanged)
- **StartupScorer** — relevance to user's background + program prestige signal (simplified: keyword match on "startup", "founder", "AI", plus user skills)
- **GrantScorer** — keyword overlap with user's skills + deadline proximity (sooner = higher)

The `Matcher` class selects the scorer based on opportunity category.

### 5. Drafting (Drafter)

Different templates per category:

| Category | Output | Prompt |
|---|---|---|
| `job` | Cover letter | Existing drafter logic (unchanged) |
| `startup` | Pitch summary | Brief founder background + product idea relevance |
| `grant` | Proposal abstract | Problem statement + approach + expected impact |

The `Drafter` class selects the template based on opportunity category.

### 6. Application

- **Jobs** — existing flow: cover letter → submit via Greenhouse/Lever/Generic
- **Startups** — new flow: generate pitch summary → direct user to program URL (most accelerators require their own application portal)
- **Grants** — new flow: generate proposal abstract → direct user to grant URL

The `ApplicationManager` routes based on category.

### 7. UI — Dashboard Pages

**Navigation change:** The sidebar gets a dropdown or sub-items:
- Opportunities
  - Jobs
  - Startups
  - Grants

Each page has the same layout but different columns:

**Jobs** (`/opportunities/jobs`): Title, Company, Location, Salary, Remote, Score, Status
**Startups** (`/opportunities/startups`): Title, Program, Stage, Amount, Deadline, Score, Status
**Grants** (`/opportunities/grants`): Title, Provider, Amount, Deadline, Score, Status

The filter API (`/api/opportunities`) gains a `category` query parameter.

The detail modal shows category-appropriate fields.

**Review page** (`/review`) also filters by category — users review jobs and startups separately.

### 8. File changes

| File | Change |
|---|---|
| `job_bot/database/models.py` | Add `category`, `program`, `stage`, `amount` columns |
| `job_bot/discovery/base.py` | Add `category`, `program`, `stage`, `amount` to dataclass |
| `job_bot/discovery/orchestrator.py` | Pass category through to repo |
| `job_bot/database/repository.py` | Filter by category, per-category stats |
| `job_bot/intelligence/matcher.py` | Strategy pattern: JobScorer/StartupScorer/GrantScorer |
| `job_bot/intelligence/drafter.py` | Per-category templates |
| `job_bot/application/manager.py` | Route by category |
| `job_bot/dashboard/server.py` | Category-filtered routes + API |
| `job_bot/dashboard/templates/base.html` | Sidebar with sub-items |
| `job_bot/dashboard/templates/opportunities.html` | → Split into `jobs_list.html`, `startups_list.html`, `grants_list.html` or reuse with category param |
| `job_bot/review/manager.py` | Category filter for pending review |

## Out of scope

- Adding new scrapers (existing ones just get re-tagged)
- Database migration scripts (use SQLAlchemy metadata to add columns, existing data gets inferred category at first read)
- Advanced startup scoring (prestige ranking, network graph) — starts with simple keyword/skill matching
