# Job Application Bot - Design Specification

**Date:** 2026-06-08
**Status:** Draft

## Context

A personal automation bot for discovering and applying to international 1099/contractor jobs, remote work, grants, and fellowships accessible from Rwanda. The bot scrapes diverse sources (company career pages, Google Search, grant databases, job boards), uses local LLMs to match the user's profile against opportunities, prepares tailored applications, and submits them with human-in-the-loop approval.

## Architecture: Monolithic Orchestrator with Plugin Architecture

A single Python application (`job_bot/`) with clean modular boundaries. Components communicate via in-process function calls and a shared SQLite database. A plugin system allows adding scrapers and application platform handlers without modifying the core.

```
job_bot/
├── __init__.py
├── main.py                    # Entry point, CLI
├── config.py                  # YAML config loader
├── database/
│   ├── __init__.py
│   ├── models.py              # SQLAlchemy models
│   └── repository.py          # CRUD operations
├── profile/
│   ├── __init__.py
│   ├── models.py              # User profile, CV, bio
│   └── vector_store.py        # ChromaDB integration
├── discovery/
│   ├── __init__.py
│   ├── base.py                # Abstract base scraper
│   ├── registry.py            # Plugin registry
│   ├── google_search.py       # Serper API scraper
│   ├── linkedin.py            # LinkedIn scraping
│   ├── indeed.py              # Indeed scraping
│   ├── ycombinator.py         # YC job board
│   ├── grants.py              # Grant/fellowship databases
│   ├── company_pages.py       # Target company career pages
│   └── scheduler.py           # APScheduler config
├── intelligence/
│   ├── __init__.py
│   ├── providers/
│   │   ├── base.py            # Abstract LLM provider
│   │   ├── ollama.py          # Local Ollama
│   │   ├── gemini.py          # Google Gemini API
│   │   └── openai.py          # OpenAI API (optional)
│   ├── matcher.py             # Profile-opportunity matching
│   ├── drafter.py             # Cover letter generation
│   └── embeddings.py          # Vector embeddings for profile
├── application/
│   ├── __init__.py
│   ├── base.py                # Abstract applier
│   ├── registry.py            # Platform registry
│   ├── platforms/
│   │   ├── greenhouse.py      # Greenhouse ATS
│   │   ├── lever.py           # Lever ATS
│   │   ├── workday.py         # Workday ATS
│   │   ├── ashby.py           # Ashby ATS
│   │   └── generic.py         # Generic form filler with Playwright
│   ├── form_filler.py         # LLM-guided field mapping
│   └── draft_manager.py       # Draft approval workflow
├── notifications/
│   ├── __init__.py
│   ├── base.py                # Abstract notifier
│   ├── whatsapp.py            # Meta WhatsApp Cloud API
│   └── email.py               # SMTP fallback
├── cli/
│   ├── __init__.py
│   ├── commands.py            # Typer commands
│   └── prompts.py             # Interactive prompts
└── utils/
    ├── __init__.py
    ├── logging.py             # Structured logging (structlog)
    ├── retry.py               # Retry with exponential backoff
    └── encryption.py          # Credential encryption
```

## Components

### 1. Database Layer (SQLite → PostgreSQL)

**Tables:**
- `opportunities`: id, title, company, description, url, source, deadline, salary_range, location, remote, status (new/matched/applied/rejected), score, matched_at, applied_at
- `applications`: id, opportunity_id, cover_letter, answers_json, platform (greenhouse/lever/custom), status (draft/submitted/accepted/rejected), submitted_at, screenshot_path
- `user_profile`: id, name, email, phone, cv_text, bio, skills_json, preferences_json
- `audit_log`: id, action, component, details_json, created_at

**Vector Store (ChromaDB):**
- User profile embeddings (CV, bio, skills)
- Past cover letters for reference

### 2. Discovery Layer

**Scraper Interface:**
```python
class BaseScraper(ABC):
    name: str
    async def discover(self, criteria: SearchCriteria) -> List[Opportunity]
```

**Built-in Scrapers:**
- `GoogleSearchScraper`: Uses Serper API to search `"1099 contractor AI remote Africa"`, fellowship directories, grant listings
- `LinkedInScraper`: Playwright-based scraping of LinkedIn Jobs
- `IndeedScraper`: Playwright-based Indeed scraping
- `YCScraper`: Y Combinator job board API/scraping
- `GrantScraper`: Grant databases (grants.gov, ResearchGate, fellowship directories)
- `CompanyPagesScraper`: Target list of company career pages
- `CustomLinkScraper`: Handle one-off links the user shares

**Scheduling:** APScheduler with configurable intervals (daily default).

### 3. Intelligence Layer

**LLM Provider Interface:**
```python
class LLMProvider(ABC):
    async def generate(self, prompt: str, system: str = None) -> str
    async def embed(self, text: str) -> List[float]
```

**Providers:**
| Provider | Models | When to Use |
|----------|--------|-------------|
| Ollama | `llama3.1:8b`, `mistral:7b`, `nomic-embed-text` | Default, free, local, embeddings |
| Google Gemini | `gemini-1.5-pro`, `gemini-1.5-flash`, `text-embedding-004` | Higher quality reasoning |
| OpenAI | `gpt-4o`, `gpt-4o-mini` | Optional fallback |

**Config-driven selection:**
```yaml
llm:
  provider: ollama       # or gemini, openai
  model: llama3.1:8b    # or gemini-1.5-flash, gpt-4o-mini
  temperature: 0.3
  profile_embedding: nomic-embed-text  # or text-embedding-004
```

**Pipeline:**
1. **Filtering**: LLM scores opportunities against user profile (skills, location, remote preference, salary)
2. **Matching**: Embedding similarity between profile and opportunity description
3. **Drafting**: Generate cover letter + any required answers using structured output
4. **Quality check**: LLM self-review of generated content

### 4. Application Layer

**Platform Detection:**
```python
class BaseApplier(ABC):
    platforms: List[str]  # URL patterns
    async def apply(self, opportunity: Opportunity, draft: Draft) -> ApplicationResult
```

**Built-in Appliers:**
- `GreenhouseApplier`: Detects `boards.greenhouse.io/*`, maps fields via known selectors
- `LeverApplier`: Detects `jobs.lever.co/*`
- `WorkdayApplier`: Detects `myworkdayjobs.com/*`, handles multi-step forms
- `AshbyApplier`: Detects `jobs.ashbyhq.com/*`
- `GoogleFormApplier`: Detects `docs.google.com/forms/*`
- `CustomFormApplier`: Generic fallback with LLM-guided field detection

**Form Filling Strategy:**
1. Parse page structure (read form fields, labels, placeholders)
2. LLM maps user profile data to form fields
3. Playwright fills and submits
4. Screenshot result for audit

### 5. Notification Layer (WhatsApp)

**Meta WhatsApp Cloud API:**
- Templates for: `new_matches`, `draft_ready`, `submission_success`, `submission_failed`
- Interactive replies for: approve/reject drafts
- Webhook endpoint for receiving user commands

**Message Flow:**
```
Bot: "Found 5 new matches today. Top match: AI Engineer @ Stripe (Remote, $80-120/hr). Review? [Yes/Skip/Details]"
User: "Details"
Bot: [Sends summary of match + draft cover letter]
Bot: "Approve and submit? [Approve/Edit/Reject]"
User: "Approve"
Bot: [Submits application]
Bot: "Submitted! Confirmation ID: ABC123"
```

### 6. CLI Layer (Typer)

**Commands:**
```
job-bot discover             # Run discovery now
job-bot review               # Show pending matches
job-bot apply <id>           # Prepare + send application
job-bot status               # Application tracking dashboard
job-bot config set <key> <value>  # Update config
job-bot profile import <file>    # Import CV/bio
job-bot sources list          # List active scrapers
job-bot sources add <type> [url]  # Add custom source
```

### 7. Config (`config.yaml`)

```yaml
profile:
  name: "Your Name"
  email: "you@email.com"
  phone: "+250..."
  cv_path: "profile/cv.pdf"
  skills: ["Python", "React", "AI/ML", "Product Design"]

llm:
  provider: ollama
  model: llama3.1:8b
  embedding_model: nomic-embed-text

discovery:
  interval_hours: 24
  sources:
    google_search: true
    linkedin: true
    indeed: false
    ycombinator: true
    grants: true
    companies:
      - stripe
      - openai
      - anthropic
      - github
  serper_api_key: "${SERPER_API_KEY}"
  grants_keywords: ["AI research", "tech fellowship", "startup grant"]

application:
  human_approval: true
  max_applications_per_run: 5
  save_drafts: true
  headless: true

notifications:
  whatsapp:
    enabled: true
    phone_number_id: "${WHATSAPP_PHONE_ID}"
    token: "${WHATSAPP_TOKEN}"
    recipient: "+250..."

database:
  path: "data/job_bot.db"
  vector_path: "data/vectors"
```

## Error Handling & Reliability

- **Retry with exponential backoff** (3 attempts, 1s/4s/15s delays)
- **Structured logging** with structlog (JSON format, redacted PII)
- **Screenshot on failure** during form submission
- **Audit log** for every action (who, what, when, result)
- **Graceful degradation**: If Ollama fails, fallback to Gemini. If Gemini fails, mark and continue.
- **Idempotency**: Track submitted opportunities to prevent duplicates

## Security

- Credentials in environment variables (loaded via python-dotenv)
- Encrypted storage for WhatsApp tokens (cryptography Fernet)
- No PII in logs (redact emails, phone numbers, names)
- Local LLM keeps CV data on-device
- Human approval required before any submission

## Future Considerations (Not MVP)

- Streamlit dashboard
- PostgreSQL migration
- Email inbox scanning (Gmail API for recruiter replies)
- Multi-user support
- Docker deployment

## Development Plan (MVP)

1. Project scaffold + config + database models
2. User profile import (CV parsing, vector store)
3. CLI commands skeleton
4. Discovery: Google Search scraper
5. Discovery: LinkedIn scraper
6. Discovery: Grant/fellowship scraper
7. Discovery: Company pages scraper
8. Intelligence: LLM provider abstraction + Ollama
9. Intelligence: LLM provider + Gemini
10. Intelligence: Matcher + Drafter
11. Application: Greenhouse/Lever platform
12. Application: Workday platform
13. Application: Generic form filler
14. Notifications: WhatsApp integration
15. Notifications: CLI review workflow
16. Scheduling + end-to-end integration
17. Testing + documentation
