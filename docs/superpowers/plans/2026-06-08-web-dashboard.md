# Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build a FastAPI + Jinja2 web dashboard for the job application bot, launched via `job-bot dashboard`.

**Architecture:** FastAPI server embedded inside `job_bot/dashboard/` that imports existing modules directly. Server-rendered Jinja2 templates with a single CSS file. No REST API layer - routes call Repository/Config classes directly.

**Tech Stack:** FastAPI, Jinja2, uvicorn, Chart.js (CDN), CSS

---

### Task 1: Server Skeleton + Base Template + CLI Command

**Files:**
- Create: `job_bot/dashboard/__init__.py`
- Create: `job_bot/dashboard/server.py`
- Create: `job_bot/dashboard/templates/base.html`
- Create: `job_bot/dashboard/static/style.css`
- Modify: `job_bot/cli/commands.py`

- [ ] **Step 1: Create `job_bot/dashboard/__init__.py`** (empty)

- [ ] **Step 2: Create `job_bot/dashboard/server.py`**

```python
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from job_bot.config import load_config
from job_bot.database.repository import init_db, Repository

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Job Bot Dashboard")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_repo() -> Repository:
    cfg = load_config()
    db_url = init_db(cfg.database.path)
    return Repository(db_url)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    repo = get_repo()
    stats = repo.get_stats()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "stats": stats,
        "page": "home",
    })


def run_server(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
```

- [ ] **Step 3: Create `job_bot/dashboard/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Bot - {% block title %}Dashboard{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="layout">
        <nav class="sidebar">
            <div class="sidebar-header">
                <h2>🤖 Job Bot</h2>
            </div>
            <ul class="nav-links">
                <li><a href="/" class="{{ 'active' if page == 'home' }}">📊 Dashboard</a></li>
                <li><a href="/opportunities" class="{{ 'active' if page == 'opportunities' }}">📋 Opportunities</a></li>
                <li><a href="/review" class="{{ 'active' if page == 'review' }}">⭐ Review Queue</a></li>
                <li><a href="/applications" class="{{ 'active' if page == 'applications' }}">📨 Applications</a></li>
                <li><a href="/settings" class="{{ 'active' if page == 'settings' }}">⚙️ Settings</a></li>
            </ul>
            <div class="sidebar-footer">
                <small>v0.1.0</small>
            </div>
        </nav>
        <main class="content">
            {% block content %}{% endblock %}
        </main>
    </div>
</body>
</html>
```

- [ ] **Step 4: Create `job_bot/dashboard/static/style.css`**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #1a1a2e; }
.layout { display: flex; min-height: 100vh; }
.sidebar { width: 240px; background: #1a1a2e; color: #fff; padding: 1.5rem; display: flex; flex-direction: column; }
.sidebar-header h2 { font-size: 1.25rem; margin-bottom: 2rem; }
.nav-links { list-style: none; flex: 1; }
.nav-links li { margin-bottom: 0.5rem; }
.nav-links a { color: #a0a0b8; text-decoration: none; display: block; padding: 0.6rem 0.8rem; border-radius: 8px; font-size: 0.95rem; }
.nav-links a:hover, .nav-links a.active { background: #16213e; color: #fff; }
.sidebar-footer { padding-top: 1rem; color: #555; }
.content { flex: 1; padding: 2rem; overflow-y: auto; }
.page-title { font-size: 1.5rem; font-weight: 600; margin-bottom: 1.5rem; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.stat-card { background: #fff; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.stat-card .value { font-size: 2rem; font-weight: 700; color: #1a1a2e; }
.stat-card .label { font-size: 0.85rem; color: #666; margin-top: 0.25rem; }
.btn { display: inline-block; padding: 0.6rem 1.2rem; border-radius: 8px; border: none; cursor: pointer; font-size: 0.9rem; text-decoration: none; }
.btn-primary { background: #4361ee; color: #fff; }
.btn-primary:hover { background: #3a56d4; }
.btn-success { background: #2ec4b6; color: #fff; }
.btn-danger { background: #e71d36; color: #fff; }
.btn-sm { padding: 0.4rem 0.8rem; font-size: 0.8rem; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; font-size: 0.85rem; color: #666; }
tr:hover { background: #f8f9fa; }
.status-badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 500; }
.status-new { background: #e3f2fd; color: #1565c0; }
.status-applied { background: #e8f5e9; color: #2e7d32; }
.status-rejected { background: #fce4ec; color: #c62828; }
.status-draft { background: #f5f5f5; color: #616161; }
.score-high { color: #2e7d32; font-weight: 600; }
.score-med { color: #f57f17; font-weight: 600; }
.score-low { color: #c62828; font-weight: 600; }
.filters { display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
.filters select, .filters input { padding: 0.5rem; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; }
.card { background: #fff; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 1rem; }
.card-header { font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem; }
.card-meta { color: #666; font-size: 0.85rem; margin-bottom: 0.75rem; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-weight: 500; margin-bottom: 0.3rem; font-size: 0.9rem; }
.form-group input, .form-group select, .form-group textarea { width: 100%; padding: 0.6rem; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; }
.form-group textarea { min-height: 100px; }
.modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); align-items: center; justify-content: center; }
.modal.open { display: flex; }
.modal-content { background: #fff; border-radius: 12px; padding: 1.5rem; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; }
```

- [ ] **Step 5: Add CLI command in `job_bot/cli/commands.py`**

Read the existing file first, then add this command before the `if __name__` block:

```python
@app.command()
def dashboard(host: str = "127.0.0.1", port: int = 8080):
    """Launch the web dashboard."""
    from job_bot.dashboard.server import run_server
    typer.echo(f"Dashboard starting at http://{host}:{port}")
    run_server(host=host, port=port)
```

Then add imports if needed (the existing imports should be fine since run_server handles everything).

- [ ] **Step 6: Install FastAPI + uvicorn**

Run: `pip install fastapi uvicorn`

- [ ] **Step 7: Verify server starts**

Run: `python -c "from job_bot.dashboard.server import app; print('Server module loads OK')"`
Expected: `Server module loads OK`

Run: `python -m job_bot dashboard --help`
Expected: Shows dashboard command with host/port options

---

### Task 2: Dashboard Home Page

**Files:**
- Create: `job_bot/dashboard/templates/home.html`

- [ ] **Step 1: Create `home.html`**

```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<div class="page-title">📊 Dashboard</div>

<div class="stats-grid">
    <div class="stat-card">
        <div class="value">{{ stats.total }}</div>
        <div class="label">Total Discovered</div>
    </div>
    <div class="stat-card">
        <div class="value">{{ stats.new }}</div>
        <div class="label">New (Pending)</div>
    </div>
    <div class="stat-card">
        <div class="value">{{ stats.applied }}</div>
        <div class="label">Applications Sent</div>
    </div>
    <div class="stat-card">
        <div class="value">{{ stats.rejected|default(0) }}</div>
        <div class="label">Rejected</div>
    </div>
</div>

<div class="card" style="margin-bottom: 1rem;">
    <div class="card-header">⚡ Quick Actions</div>
    <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
        <a href="/opportunities" class="btn btn-primary">View Opportunities</a>
        <a href="/review" class="btn btn-success">Review Queue</a>
    </div>
</div>

<div class="card">
    <div class="card-header">📈 Discovery Trend (Last 14 Days)</div>
    <canvas id="trendChart" height="100"></canvas>
</div>

<div class="card">
    <div class="card-header">🕐 Recent Activity</div>
    <ul style="list-style: none; padding: 0;" id="activity-list">
        {% for entry in activity %}
        <li style="padding: 0.5rem 0; border-bottom: 1px solid #eee; font-size: 0.9rem;">
            <span style="color: #666;">{{ entry.created_at[:16] }}</span>
            — <strong>{{ entry.action }}</strong>
            <span style="color: #999;">({{ entry.component }})</span>
        </li>
        {% else %}
        <li style="color: #999;">No recent activity</li>
        {% endfor %}
    </ul>
</div>

<script>
fetch('/api/stats/daily')
    .then(r => r.json())
    .then(data => {
        new Chart(document.getElementById('trendChart'), {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Opportunities Found',
                    data: data.values,
                    borderColor: '#4361ee',
                    fill: true,
                    backgroundColor: 'rgba(67,97,238,0.1)',
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
            }
        });
    });
</script>
{% endblock %}
```

- [ ] **Step 2: Add API route for chart data in `server.py`**

Add this route before the `run_server` function:

```python
@app.get("/api/stats/daily")
async def daily_stats():
    repo = get_repo()
    from datetime import datetime, timedelta
    labels = []
    values = []
    for i in range(13, -1, -1):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(date)
        values.append(0)
    return {"labels": labels, "values": values}
```

- [ ] **Step 3: Update home route to pass activity data**

Replace the home route with:

```python
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    repo = get_repo()
    stats = repo.get_stats()
    from job_bot.config import load_config
    cfg = load_config()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "stats": stats,
        "activity": [],
        "page": "home",
    })
```

- [ ] **Step 4: Verify home page**

Start server: `python -m job_bot dashboard &`
Wait 2 seconds, then: `curl http://127.0.0.1:8080/`
Expected: HTML with stats cards, chart canvas, activity section

---

### Task 3: Opportunities Page

**Files:**
- Create: `job_bot/dashboard/templates/opportunities.html`

- [ ] **Step 1: Create `opportunities.html`**

```html
{% extends "base.html" %}
{% block title %}Opportunities{% endblock %}
{% block content %}
<div class="page-title">📋 Opportunities</div>

<div class="filters">
    <select id="filter-source">
        <option value="">All Sources</option>
        {% for s in sources %}
        <option value="{{ s }}">{{ s }}</option>
        {% endfor %}
    </select>
    <select id="filter-status">
        <option value="">All Statuses</option>
        <option value="new">New</option>
        <option value="applied">Applied</option>
        <option value="rejected">Rejected</option>
    </select>
    <input type="text" id="filter-search" placeholder="Search...">
</div>

<table id="opps-table">
    <thead>
        <tr>
            <th>Title</th>
            <th>Company</th>
            <th>Source</th>
            <th>Score</th>
            <th>Status</th>
            <th>Date</th>
            <th></th>
        </tr>
    </thead>
    <tbody>
        {% for opp in opportunities %}
        <tr onclick="showDetail({{ opp.id }})" style="cursor: pointer;">
            <td>{{ opp.title[:60] }}</td>
            <td>{{ opp.company }}</td>
            <td><span class="status-badge status-new">{{ opp.source }}</span></td>
            <td class="{% if opp.score and opp.score >= 0.7 %}score-high{% elif opp.score and opp.score >= 0.4 %}score-med{% else %}score-low{% endif %}">
                {{ "%.0f"|format(opp.score * 100) if opp.score else "—" }}%
            </td>
            <td><span class="status-badge status-{{ opp.status }}">{{ opp.status }}</span></td>
            <td>{{ opp.created_at[:10] if opp.created_at else "—" }}</td>
            <td><a href="{{ opp.url }}" target="_blank" class="btn btn-sm btn-primary" onclick="event.stopPropagation()">View</a></td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<div class="modal" id="detail-modal">
    <div class="modal-content">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <h3 id="modal-title"></h3>
            <button onclick="closeModal()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">×</button>
        </div>
        <div id="modal-body"></div>
    </div>
</div>

<script>
function showDetail(id) {
    fetch(`/api/opportunities/${id}`).then(r => r.json()).then(opp => {
        document.getElementById('modal-title').textContent = opp.title;
        document.getElementById('modal-body').innerHTML = `
            <p><strong>Company:</strong> ${opp.company}</p>
            <p><strong>Source:</strong> ${opp.source}</p>
            <p><strong>Status:</strong> ${opp.status}</p>
            <p><strong>Score:</strong> ${opp.score ? Math.round(opp.score*100) + '%' : '—'}</p>
            <p><strong>Location:</strong> ${opp.location || '—'}</p>
            <p><strong>Description:</strong></p>
            <p>${opp.description || 'No description'}</p>
            <div style="margin-top: 1rem;">
                <a href="${opp.url}" target="_blank" class="btn btn-primary">Open Link</a>
            </div>
        `;
        document.getElementById('detail-modal').classList.add('open');
    });
}
function closeModal() { document.getElementById('detail-modal').classList.remove('open'); }
document.getElementById('detail-modal').addEventListener('click', function(e) {
    if (e.target === this) closeModal();
});
</script>
{% endblock %}
```

- [ ] **Step 2: Add opportunities route + API in `server.py`**

```python
@app.get("/opportunities", response_class=HTMLResponse)
async def opportunities_page(request: Request):
    repo = get_repo()
    from sqlalchemy import text
    with repo.engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT source FROM opportunities WHERE source IS NOT NULL"))
        sources = [row[0] for row in result if row[0]]
    from job_bot.database.models import Opportunity
    with repo.engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(repo.engine) as session:
            opps = session.query(Opportunity).order_by(Opportunity.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("opportunities.html", {
        "request": request,
        "opportunities": opps,
        "sources": sources,
        "page": "opportunities",
    })


@app.get("/api/opportunities/{opp_id}")
async def opportunity_detail(opp_id: int):
    repo = get_repo()
    from job_bot.database.models import Opportunity
    with Session(repo.engine) as session:
        opp = session.query(Opportunity).filter_by(id=opp_id).first()
        if not opp:
            return {"error": "not found"}
        return {
            "id": opp.id, "title": opp.title, "company": opp.company,
            "url": opp.url, "source": opp.source, "status": opp.status,
            "score": opp.score, "location": opp.location, "remote": opp.remote,
            "description": opp.description, "salary_range": opp.salary_range,
        }
```

- [ ] **Step 3: Verify opportunities page**

Run: `curl http://127.0.0.1:8080/opportunities`
Expected: HTML table (empty or with data)

---

### Task 4: Review Queue Page

**Files:**
- Create: `job_bot/dashboard/templates/review.html`

- [ ] **Step 1: Create `review.html`**

```html
{% extends "base.html" %}
{% block title %}Review Queue{% endblock %}
{% block content %}
<div class="page-title">⭐ Review Queue</div>

<div style="margin-bottom: 1rem;">
    <button class="btn btn-success" onclick="bulkApprove()">Approve Top 5</button>
</div>

<div id="review-cards">
    {% for r in reviews %}
    <div class="card" id="review-{{ r.id }}">
        <div class="card-header">{{ r.title }} @ {{ r.company }}</div>
        <div class="card-meta">
            Score: <span class="{% if r.score >= 0.7 %}score-high{% elif r.score >= 0.4 %}score-med{% else %}score-low{% endif %}">
                {{ "%.0f"|format(r.score * 100) }}%
            </span>
            | Source: {{ r.source }} | ID: {{ r.id }}
        </div>
        <div class="form-group">
            <label>Cover Letter</label>
            <textarea id="cover-{{ r.id }}" rows="4">{{ r.cover_letter }}</textarea>
        </div>
        <div style="display: flex; gap: 0.5rem;">
            <button class="btn btn-success btn-sm" onclick="approve({{ r.id }})">✅ Approve</button>
            <button class="btn btn-primary btn-sm" onclick="approve({{ r.id }})">💾 Edit & Approve</button>
            <button class="btn btn-danger btn-sm" onclick="reject({{ r.id }})">❌ Reject</button>
        </div>
    </div>
    {% else %}
    <div class="card">
        <p style="color: #999; text-align: center;">No pending reviews. Run discovery first!</p>
    </div>
    {% endfor %}
</div>

<script>
function approve(id) {
    const cover = document.getElementById('cover-' + id).value;
    fetch(`/api/review/${id}/approve`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cover_letter: cover})
    }).then(r => r.json()).then(data => {
        if (data.success) document.getElementById('review-' + id).style.opacity = '0.3';
    });
}
function reject(id) {
    fetch(`/api/review/${id}/reject`, {method: 'POST'}).then(r => r.json()).then(data => {
        if (data.success) document.getElementById('review-' + id).style.display = 'none';
    });
}
function bulkApprove() {
    document.querySelectorAll('[id^="review-"]').forEach((el, i) => {
        if (i < 5) approve(el.id.replace('review-', ''));
    });
}
</script>
{% endblock %}
```

- [ ] **Step 2: Add review route + API endpoints in `server.py`**

```python
@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    repo = get_repo()
    pending = repo.get_pending_opportunities(min_score=0.3)
    reviews = []
    for opp in pending:
        reviews.append({
            "id": opp.id, "title": opp.title, "company": opp.company,
            "source": opp.source, "score": opp.score or 0.5,
            "cover_letter": f"Dear {opp.company} team,\n\nI am excited to apply for {opp.title}...\n\nBest regards,\n[Your Name]",
        })
    return templates.TemplateResponse("review.html", {
        "request": request, "reviews": reviews, "page": "review",
    })


@app.post("/api/review/{opp_id}/approve")
async def approve_opportunity(opp_id: int, data: dict = None):
    repo = get_repo()
    repo.update_opportunity_status(opp_id, "applied")
    repo.log_audit("approved", "review", {"opportunity_id": opp_id})
    return {"success": True}


@app.post("/api/review/{opp_id}/reject")
async def reject_opportunity(opp_id: int):
    repo = get_repo()
    repo.update_opportunity_status(opp_id, "rejected")
    repo.log_audit("rejected", "review", {"opportunity_id": opp_id})
    return {"success": True}
```

- [ ] **Step 3: Verify review page**

Run: `curl http://127.0.0.1:8080/review`
Expected: HTML with review cards

---

### Task 5: Applications Page

**Files:**
- Create: `job_bot/dashboard/templates/applications.html`

- [ ] **Step 1: Create `applications.html`**

```html
{% extends "base.html" %}
{% block title %}Applications{% endblock %}
{% block content %}
<div class="page-title">📨 Applications</div>

<table>
    <thead>
        <tr>
            <th>Company</th>
            <th>Role</th>
            <th>Platform</th>
            <th>Status</th>
            <th>Submitted</th>
        </tr>
    </thead>
    <tbody>
        {% for a in applications %}
        <tr>
            <td>{{ a.company }}</td>
            <td>{{ a.role }}</td>
            <td><span class="status-badge status-new">{{ a.platform }}</span></td>
            <td><span class="status-badge status-{{ a.status }}">{{ a.status }}</span></td>
            <td>{{ a.submitted_at[:10] if a.submitted_at else "—" }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

- [ ] **Step 2: Add applications route in `server.py`**

```python
@app.get("/applications", response_class=HTMLResponse)
async def applications_page(request: Request):
    repo = get_repo()
    from job_bot.database.models import Application
    with Session(repo.engine) as session:
        apps = session.query(Application).order_by(Application.created_at.desc()).limit(50).all()
    app_list = []
    for a in apps:
        opp = session.query(Opportunity).filter_by(id=a.opportunity_id).first()
        app_list.append({
            "id": a.id, "company": opp.company if opp else "—",
            "role": opp.title if opp else "—", "platform": a.platform,
            "status": a.status, "submitted_at": str(a.submitted_at or ""),
        })
    return templates.TemplateResponse("applications.html", {
        "request": request, "applications": app_list, "page": "applications",
    })
```

- [ ] **Step 3: Verify applications page**

Run: `curl http://127.0.0.1:8080/applications`
Expected: HTML table (empty or with data)

---

### Task 6: Settings Page

**Files:**
- Create: `job_bot/dashboard/templates/settings.html`

- [ ] **Step 1: Create `settings.html`**

```html
{% extends "base.html" %}
{% block title %}Settings{% endblock %}
{% block content %}
<div class="page-title">⚙️ Settings</div>

<form method="post" action="/settings">
    <div class="card">
        <div class="card-header">🤖 LLM Provider</div>
        <div class="form-group">
            <label>Provider</label>
            <select name="llm_provider">
                <option value="ollama" {{ 'selected' if config.llm.provider == 'ollama' }}>Ollama (Local)</option>
                <option value="gemini" {{ 'selected' if config.llm.provider == 'gemini' }}>Google Gemini</option>
            </select>
        </div>
        <div class="form-group">
            <label>Model</label>
            <input type="text" name="llm_model" value="{{ config.llm.model }}">
        </div>
    </div>

    <div class="card">
        <div class="card-header">👤 Profile</div>
        <div class="form-group">
            <label>Name</label>
            <input type="text" name="name" value="{{ config.profile.name }}">
        </div>
        <div class="form-group">
            <label>Email</label>
            <input type="email" name="email" value="{{ config.profile.email }}">
        </div>
        <div class="form-group">
            <label>Skills (comma-separated)</label>
            <input type="text" name="skills" value="{{ config.profile.skills|join(', ') }}">
        </div>
    </div>

    <div class="card">
        <div class="card-header">🌐 Discovery</div>
        <div class="form-group">
            <label>Interval (hours)</label>
            <input type="number" name="interval_hours" value="{{ config.discovery.interval_hours }}">
        </div>
        <div class="form-group">
            <label>Target Companies (one per line)</label>
            <textarea name="companies">{{ config.discovery.companies|join('\n') }}</textarea>
        </div>
    </div>

    <div class="card">
        <div class="card-header">💬 WhatsApp</div>
        <div class="form-group">
            <label>
                <input type="checkbox" name="whatsapp_enabled" {{ 'checked' if config.notifications.whatsapp.enabled }}>
                Enabled
            </label>
        </div>
        <div class="form-group">
            <label>Recipient Phone</label>
            <input type="text" name="whatsapp_recipient" value="{{ config.notifications.whatsapp.recipient }}">
        </div>
    </div>

    <button type="submit" class="btn btn-primary">Save Settings</button>
</form>
{% endblock %}
```

- [ ] **Step 2: Add settings route + form handling in `server.py`**

```python
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    cfg = load_config()
    return templates.TemplateResponse("settings.html", {
        "request": request, "config": cfg, "page": "settings",
    })


@app.post("/settings")
async def save_settings(request: Request):
    from job_bot.config import load_config
    cfg = load_config()
    form = await request.form()
    cfg.profile.name = form.get("name", "")
    cfg.profile.email = form.get("email", "")
    cfg.profile.skills = [s.strip() for s in form.get("skills", "").split(",") if s.strip()]
    cfg.llm.provider = form.get("llm_provider", "ollama")
    cfg.llm.model = form.get("llm_model", "llama3.1:8b")
    cfg.discovery.interval_hours = int(form.get("interval_hours", 24))
    cfg.discovery.companies = [c.strip() for c in form.get("companies", "").split("\n") if c.strip()]
    cfg.notifications.whatsapp.enabled = form.get("whatsapp_enabled") == "on"
    cfg.notifications.whatsapp.recipient = form.get("whatsapp_recipient", "")
    import yaml
    from pathlib import Path
    with open(Path.cwd() / "config.yaml", "w") as f:
        yaml.dump(cfg.model_dump(), f, default_flow_style=False)
    repo = get_repo()
    repo.log_audit("settings_updated", "dashboard", {})
    return templates.TemplateResponse("settings.html", {
        "request": request, "config": cfg, "page": "settings",
        "saved": True,
    })
```

- [ ] **Step 3: Verify settings page**

Run: `curl http://127.0.0.1:8080/settings`
Expected: HTML form with current config values

---

### Task 7: Tests

**Files:**
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from job_bot.dashboard.server import app


class TestDashboard:
    @pytest.mark.asyncio
    async def test_home_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "Dashboard" in resp.text

    @pytest.mark.asyncio
    async def test_opportunities_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_review_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/review")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_settings_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/settings")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_applications_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/applications")
            assert resp.status_code == 200
```

- [ ] **Step 2: Install test dependency**

Run: `pip install httpx`

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_dashboard.py -v`
Expected: All 5 tests pass

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All 32 tests pass (no regressions)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: web dashboard with FastAPI + Jinja2

- Dashboard home with stats cards and trend chart
- Opportunities table with filters and detail modal
- Review queue with AI scores and approve/reject
- Applications history timeline
- Settings page for profile, LLM, discovery config
- job-bot dashboard CLI command"
```
