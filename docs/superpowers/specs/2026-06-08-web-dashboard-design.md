# Web Dashboard - Design Specification

**Date:** 2026-06-08
**Status:** Draft

## Overview
A web-based GUI for the job application bot, providing visualization, management, and control of all bot functions. Built as an integrated FastAPI server launched via `job-bot dashboard`.

## Architecture

FastAPI server embedded inside `job_bot/` that imports existing modules directly (no REST API layer). Templates rendered server-side with Jinja2.

```
job_bot/dashboard/
├── __init__.py
├── server.py              # FastAPI app, routes, form handling
├── templates/
│   ├── base.html          # Layout shell (nav, sidebar, CSS/JS)
│   ├── home.html          # Dashboard home
│   ├── opportunities.html # Opportunities table
│   ├── review.html        # Review queue
│   ├── applications.html  # Application history
│   └── settings.html      # Profile & config
└── static/
    ├── style.css          # Dashboard styling
    └── script.js          # Interactivity (filters, charts, modals)
```

## Pages

### 1. Dashboard Home (`/`)
- 4 stat cards with icons: Total Discovered, New This Week, Applications Sent, Avg Match Score
- Line chart (Canvas.js): Opportunities found per day over last 14 days
- Recent activity feed: last 10 audit log entries with timestamps
- Quick action buttons: Run Discovery, Open Review Queue

### 2. Opportunities (`/opportunities`)
- Sortable/filterable table with columns: Title, Company, Source, Score, Status, Date
- Filters: source dropdown, status dropdown, score slider, date range
- Search by keyword
- Row click → modal with full details: description, URL, deadline, + "Review" button

### 3. Review Queue (`/review`)
- Card-based layout, one per pending opportunity
- Each card: Title + Company, AI match score (0-100% with color coding), skill match breakdown, editable cover letter textarea
- Action buttons: Approve, Edit & Approve (saves cover letter changes), Reject
- Bulk action: Approve Top 5

### 4. Applications (`/applications`)
- Table: Company, Role, Platform, Status, Date Submitted, Last Update
- Status badges with color coding (Draft=grey, Submitted=blue, Reviewed=yellow, Replied=purple, Accepted=green, Rejected=red)
- Click for timeline of status changes

### 5. Settings (`/settings`)
- LLM Provider: select (ollama/gemini) + model text input
- Profile: name, email, bio, skills (comma-separated input), CV upload
- Discovery: checkboxes per source, companies textarea, interval hours
- WhatsApp: enable toggle, phone number, test message button

## Technical Details

- **Framework:** FastAPI + Jinja2Templates
- **Styling:** Single CSS file, no framework (lightweight)
- **Charts:** Simple Canvas.js inline (no extra dependencies)
- **Icons:** Unicode/emoji (no icon library)
- **State:** Reads/writes via existing `job_bot.database.repository.Repository` and `job_bot.config.load_config/save_config`
- **Launch:** `job-bot dashboard` CLI command starts uvicorn on `localhost:8080`
- **Data refresh:** Page reload (no websockets for MVP)

## Implementation Plan

### Task 1: Server skeleton + base template
- `server.py` with FastAPI app, Jinja2 config, static files mount
- `base.html` with navigation sidebar
- `dashboard` CLI command
- Static CSS with dashboard layout

### Task 2: Home page
- Stats from Repository.get_stats() + recent audit log
- Chart data from audit log aggregation
- Template + route

### Task 3: Opportunities page
- Full table with all filters
- Detail modal
- Template + route

### Task 4: Review queue page
- Card layout with AI scores
- Editable cover letters
- Approve/reject actions (writes to DB)
- Template + route

### Task 5: Applications page
- Table with status badges
- Timeline view
- Template + route

### Task 6: Settings page
- All forms (profile, LLM, discovery config, WhatsApp)
- Form submission handling
- Template + route

### Task 7: Tests
- Test server startup
- Test page rendering
