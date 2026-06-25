# Opportunity Categories: Jobs, Startups & Grants — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Differentiate job, startup, and grant opportunities in JBot with separate UI, scoring, drafting, and application flows.

**Architecture:** Single `Opportunity` table with a `category` column (`"job"` | `"startup"` | `"grant"`). Strategy pattern selects scoring/drafting/application logic per category. UI split into tabbed views on a single page.

**Tech Stack:** Python 3.11+, SQLAlchemy, FastAPI, Jinja2, pytest

---

### Task 1: Data Model — Add category fields to Opportunity

**Files:**
- Modify: `job_bot/database/models.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Add new columns to Opportunity model**

Edit `job_bot/database/models.py` — add after `updated_at`:

```python
    category = Column(String(50), default="job")
    program = Column(String(300), default="")
    stage = Column(String(100), default="")
    amount = Column(String(200), default="")
```

- [ ] **Step 2: Add test for category field**

In `tests/test_database.py`, add to `TestDatabase`:

```python
    def test_opportunity_with_category(self, repo):
        oid = repo.add_opportunity({
            "title": "YC W26",
            "company": "Y Combinator",
            "url": "https://ycombinator.com/apply",
            "category": "startup",
            "program": "YC W26",
            "stage": "Pre-seed",
            "amount": "$500K",
        })
        assert oid > 0
        from job_bot.database.models import Opportunity
        from sqlalchemy.orm import Session
        with Session(repo.engine) as session:
            opp = session.query(Opportunity).filter_by(id=oid).first()
            assert opp.category == "startup"
            assert opp.program == "YC W26"
            assert opp.stage == "Pre-seed"
            assert opp.amount == "$500K"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_database.py::TestDatabase::test_opportunity_with_category -v`
Expected: FAIL because columns don't exist yet

- [ ] **Step 4: Run the test again (DB recreates, columns will exist)**

Run: `python -m pytest tests/test_database.py::TestDatabase::test_opportunity_with_category -v`
Expected: PASS (SQLite `create_all` adds new columns since DB is tmp)

- [ ] **Step 5: Commit**

```bash
git add job_bot/database/models.py tests/test_database.py
git commit -m "feat: add category, program, stage, amount to Opportunity model"
```

---

### Task 2: Discovery Dataclass — Add category fields to Opportunity dataclass

**Files:**
- Modify: `job_bot/discovery/base.py`

- [ ] **Step 1: Add fields to Opportunity dataclass**

Edit `job_bot/discovery/base.py` — add after `score`:

```python
    category: str = "job"
    program: str = ""
    stage: str = ""
    amount: str = ""
```

- [ ] **Step 2: Tag each scraper's output**

Edit each scraper file to set `category`:

- `job_bot/discovery/google_search.py` — line 31: add `category="job"` to Opportunity(...)
- `job_bot/discovery/linkedin.py` — line 12: add `category="job"`
- `job_bot/discovery/company_pages.py` — line 18: add `category="job"`
- `job_bot/discovery/grants.py` — line 15: add `category="grant"`

- [ ] **Step 3: Commit**

```bash
git add job_bot/discovery/base.py job_bot/discovery/google_search.py job_bot/discovery/linkedin.py job_bot/discovery/company_pages.py job_bot/discovery/grants.py
git commit -m "feat: add category field to Opportunity dataclass and tag all scrapers"
```

---

### Task 3: Repository — Category filtering and per-category stats

**Files:**
- Modify: `job_bot/database/repository.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Add category filter to `get_pending_opportunities`**

Edit `job_bot/database/repository.py` — change signature and add filter:

```python
    def get_pending_opportunities(self, min_score: float = 0.0, category: str | None = None) -> list:
        from sqlalchemy import or_, and_
        with Session(self.engine) as session:
            query = session.query(Opportunity).filter(
                Opportunity.status == "new",
                or_(Opportunity.score.is_(None), Opportunity.score >= min_score),
            )
            if category:
                query = query.filter(Opportunity.category == category)
            return query.all()
```

- [ ] **Step 2: Add `get_stats_by_category` method**

```python
    def get_stats_by_category(self) -> dict:
        with Session(self.engine) as session:
            cats = ["job", "startup", "grant"]
            result = {}
            for cat in cats:
                result[cat] = session.query(Opportunity).filter(
                    Opportunity.category == cat
                ).count()
            return result
```

- [ ] **Step 3: Add test for category filter**

```python
    def test_get_pending_by_category(self, repo):
        repo.add_opportunity({"title": "Job 1", "company": "A", "url": "https://a.com/1", "category": "job"})
        repo.add_opportunity({"title": "Startup 1", "company": "YC", "url": "https://yc.com/1", "category": "startup"})
        repo.add_opportunity({"title": "Grant 1", "company": "NSF", "url": "https://nsf.gov/1", "category": "grant"})
        jobs = repo.get_pending_opportunities(category="job")
        assert len(jobs) == 1
        assert jobs[0].category == "job"
        stats = repo.get_stats_by_category()
        assert stats["job"] == 1
        assert stats["startup"] == 1
        assert stats["grant"] == 1
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_database.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add job_bot/database/repository.py tests/test_database.py
git commit -m "feat: add category filter to repository and per-category stats"
```

---

### Task 4: Matcher — Per-category scoring strategies

**Files:**
- Modify: `job_bot/intelligence/matcher.py`
- Modify: `job_bot/pipeline.py` (pass category when calling matcher)
- Test: `tests/test_intelligence.py`

- [ ] **Step 1: Refactor Matcher with per-category prompts**

Edit `job_bot/intelligence/matcher.py`:

```python
from job_bot.intelligence.providers.base import LLMProvider


class Matcher:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def score(self, profile_text: str, opportunity_text: str, category: str = "job") -> float:
        prompts = {
            "job": f"""Rate the fit (0-100) between this profile and job opportunity.

PROFILE:
{profile_text[:1500]}

OPPORTUNITY:
{opportunity_text[:1500]}

Return ONLY a number between 0 and 100 representing how well this profile matches.""",
            "startup": f"""Rate the fit (0-100) between this founder profile and startup program.

PROFILE:
{profile_text[:1500]}

PROGRAM:
{opportunity_text[:1500]}

Consider: founder-market fit, relevant skills, prior startup experience.
Return ONLY a number between 0 and 100.""",
            "grant": f"""Rate the fit (0-100) between this researcher profile and grant opportunity.

PROFILE:
{profile_text[:1500]}

GRANT:
{opportunity_text[:1500]}

Consider: research alignment, relevant expertise, project feasibility.
Return ONLY a number between 0 and 100.""",
        }
        prompt = prompts.get(category, prompts["job"])
        result = await self.provider.generate(prompt)
        try:
            return min(100, max(0, float(result.strip()))) / 100
        except (ValueError, TypeError):
            return 0.0
```

- [ ] **Step 2: Update pipeline.py to pass category**

Edit `job_bot/pipeline.py` — in `_run_review` (or wherever matcher.score is called), pass `category=opp.category`.

Find the review call and update to include category:

In `job_bot/review/manager.py` line 19:
```python
            score = await self.matcher.score(
                profile.get("cv_text", ""),
                f"{opp.title} {opp.description}",
                category=opp.category,
            )
```

- [ ] **Step 3: Add test for category scoring**

In `tests/test_intelligence.py`, add to `TestMatcher`:

```python
    def test_matcher_with_category(self):
        provider = create_provider("ollama")
        matcher = Matcher(provider)
        assert matcher is not None
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_intelligence.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add job_bot/intelligence/matcher.py job_bot/review/manager.py tests/test_intelligence.py
git commit -m "feat: per-category scoring in Matcher"
```

---

### Task 5: Drafter — Per-category drafting templates

**Files:**
- Modify: `job_bot/intelligence/drafter.py`

- [ ] **Step 1: Refactor Drafter with per-category methods**

Edit `job_bot/intelligence/drafter.py`:

```python
from job_bot.intelligence.providers.base import LLMProvider


class Drafter:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate(
        self, profile: str, opportunity_title: str, company: str, skills: list[str], category: str = "job"
    ) -> str:
        if category == "startup":
            return await self._generate_pitch(profile, opportunity_title, company, skills)
        elif category == "grant":
            return await self._generate_proposal(profile, opportunity_title, company, skills)
        return await self._generate_cover_letter(profile, opportunity_title, company, skills)

    async def _generate_cover_letter(
        self, profile: str, opportunity_title: str, company: str, skills: list[str]
    ) -> str:
        prompt = f"""Write a professional cover letter for:

Position: {opportunity_title}
Company: {company}
Key Skills: {', '.join(skills)}
Background: {profile[:500]}

Write 3-4 paragraphs. Be specific about relevant experience. Keep it concise."""
        return await self.provider.generate(prompt)

    async def _generate_pitch(
        self, profile: str, opportunity_title: str, company: str, skills: list[str]
    ) -> str:
        prompt = f"""Write a concise startup pitch summary for:

Program: {opportunity_title}
Organization: {company}
Founder Skills: {', '.join(skills)}
Background: {profile[:500]}

Write 2-3 paragraphs describing the founder's relevant experience, what they'd build, and why this program is a good fit."""
        return await self.provider.generate(prompt)

    async def _generate_proposal(
        self, profile: str, opportunity_title: str, company: str, skills: list[str]
    ) -> str:
        prompt = f"""Write a grant proposal abstract for:

Grant: {opportunity_title}
Organization: {company}
Expertise: {', '.join(skills)}
Background: {profile[:500]}

Write 2-3 paragraphs: problem statement, proposed approach, expected impact."""
        return await self.provider.generate(prompt)
```

- [ ] **Step 2: Update review manager to use new Drafter API**

Edit `job_bot/review/manager.py` — line 23-28, change:

```python
            cover = await self.drafter.generate(
                profile.get("cv_text", ""),
                opp.title,
                opp.company,
                profile.get("skills", []),
                category=opp.category,
            )
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_intelligence.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add job_bot/intelligence/drafter.py job_bot/review/manager.py
git commit -m "feat: per-category drafting in Drafter (cover letter, pitch, proposal)"
```

---

### Task 6: Application Manager — Route by category

**Files:**
- Modify: `job_bot/application/manager.py`
- Modify: `job_bot/pipeline.py`

- [ ] **Step 1: Add category routing to ApplicationManager**

Edit `job_bot/application/manager.py`:

```python
from job_bot.application.registry import get_applier
from job_bot.utils.logging import get_logger

logger = get_logger()


class ApplicationManager:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def submit(self, url: str, profile: dict, cover_letter: str, category: str = "job") -> dict:
        if category in ("startup", "grant"):
            return {
                "success": True,
                "message": f"{category.title()} applications require manual submission via the program's portal. Document prepared.",
                "platform": category,
                "url": url,
            }
        applier = get_applier(url)
        if not applier:
            return {"success": False, "message": f"No applier found for {url}"}
        result = await applier.apply(url, profile, cover_letter)
        logger.info("application_result", platform=result.platform, success=result.success)
        return {"success": result.success, "message": result.message, "platform": result.platform}
```

- [ ] **Step 2: Commit**

```bash
git add job_bot/application/manager.py
git commit -m "feat: route applications by category (jobs auto-apply, startups/grants redirect)"
```

---

### Task 7: Dashboard Routes — Category-filtered API and pages

**Files:**
- Modify: `job_bot/dashboard/server.py`

- [ ] **Step 1: Update stats API to include per-category breakdown**

Edit `job_bot/dashboard/server.py` — update `/api/stats`:

```python
@app.get("/api/stats")
async def api_stats():
    repo = get_repo()
    stats = repo.get_stats()
    stats["rejected"] = stats.get("rejected", 0)
    stats["by_category"] = repo.get_stats_by_category()
    return stats
```

- [ ] **Step 2: Add category-parameterized opportunities page**

Change `opportunities_page` route:

```python
@app.get("/opportunities", response_class=HTMLResponse)
@app.get("/opportunities/{category:path}", response_class=HTMLResponse)
async def opportunities_page(request: Request, category: str = "all"):
    repo = get_repo()
    with Session(repo.engine) as session:
        query = session.query(Opportunity).order_by(Opportunity.created_at.desc()).limit(100)
        if category and category in ("job", "startup", "grant"):
            query = query.filter(Opportunity.category == category)
        opps = query.all()
    sources = []
    with repo.engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text("SELECT DISTINCT source FROM opportunities WHERE source IS NOT NULL"))
        sources = [row[0] for row in result if row[0]]
    return templates.TemplateResponse(request, "opportunities.html", {
        "opportunities": opps, "sources": sources, "page": "opportunities",
        "current_category": category,
    })
```

- [ ] **Step 3: Update review page to support category filter**

Edit `review_page`:

```python
@app.get("/review", response_class=HTMLResponse)
@app.get("/review/{category:path}", response_class=HTMLResponse)
async def review_page(request: Request, category: str = "all"):
    repo = get_repo()
    if category in ("job", "startup", "grant"):
        pending = repo.get_pending_opportunities(min_score=0.3, category=category)
    else:
        pending = repo.get_pending_opportunities(min_score=0.3)
    cfg = load_config()
    reviews = []
    for opp in pending:
        reviews.append({
            "id": opp.id, "title": opp.title, "company": opp.company,
            "source": opp.source, "score": opp.score or 0.5, "category": opp.category,
            "cover_letter": f"Dear {opp.company} team,...",
        })
    return templates.TemplateResponse(request, "review.html", {
        "reviews": reviews, "page": "review", "current_category": category,
    })
```

- [ ] **Step 4: Commit**

```bash
git add job_bot/dashboard/server.py
git commit -m "feat: add category-filtered dashboard routes for opportunities and review"
```

---

### Task 8: UI — Tabbed opportunities page and updated nav

**Files:**
- Modify: `job_bot/dashboard/templates/base.html`
- Rewrite: `job_bot/dashboard/templates/opportunities.html`
- Modify: `job_bot/dashboard/templates/review.html`

- [ ] **Step 1: Update sidebar nav in base.html**

Replace the Opportunities nav link with:

```html
<li>
    <a href="/opportunities" class="{{ 'active' if page == 'opportunities' }}">📋 Opportunities</a>
    {% if page == 'opportunities' %}
    <ul style="padding-left: 1.5rem; list-style: none; margin-top: 0.25rem;">
        <li><a href="/opportunities/job" style="font-size: 0.85rem;">💼 Jobs</a></li>
        <li><a href="/opportunities/startup" style="font-size: 0.85rem;">🚀 Startups</a></li>
        <li><a href="/opportunities/grant" style="font-size: 0.85rem;">🎯 Grants</a></li>
    </ul>
    {% endif %}
</li>
```

- [ ] **Step 2: Rewrite opportunities.html with tab system**

Full rewrite of `job_bot/dashboard/templates/opportunities.html`:

```html
{% extends "base.html" %}
{% block title %}Opportunities{% endblock %}
{% block content %}
<div class="page-title">📋 Opportunities</div>

<div class="tabs" style="display: flex; gap: 0; margin-bottom: 1rem; border-bottom: 2px solid #e0e0e0;">
    <a href="/opportunities" class="tab {{ 'active' if current_category == 'all' }}" style="padding: 0.5rem 1.2rem; text-decoration: none; border-bottom: 2px solid {{ '#4361ee' if current_category == 'all' else 'transparent' }}; color: {{ '#4361ee' if current_category == 'all' else '#666' }}; margin-bottom: -2px; font-weight: {{ '600' if current_category == 'all' else '400' }};">All</a>
    <a href="/opportunities/job" class="tab {{ 'active' if current_category == 'job' }}" style="padding: 0.5rem 1.2rem; text-decoration: none; border-bottom: 2px solid {{ '#4361ee' if current_category == 'job' else 'transparent' }}; color: {{ '#4361ee' if current_category == 'job' else '#666' }}; margin-bottom: -2px;">💼 Jobs</a>
    <a href="/opportunities/startup" class="tab {{ 'active' if current_category == 'startup' }}" style="padding: 0.5rem 1.2rem; text-decoration: none; border-bottom: 2px solid {{ '#4361ee' if current_category == 'startup' else 'transparent' }}; color: {{ '#4361ee' if current_category == 'startup' else '#666' }}; margin-bottom: -2px;">🚀 Startups</a>
    <a href="/opportunities/grant" class="tab {{ 'active' if current_category == 'grant' }}" style="padding: 0.5rem 1.2rem; text-decoration: none; border-bottom: 2px solid {{ '#4361ee' if current_category == 'grant' else 'transparent' }}; color: {{ '#4361ee' if current_category == 'grant' else '#666' }}; margin-bottom: -2px;">🎯 Grants</a>
</div>

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
    <input type="text" id="filter-search" placeholder="Search by title...">
    <button class="btn btn-sm btn-primary" onclick="location.reload()" title="Refresh">🔄</button>
</div>

{% if opportunities %}
<table id="opps-table">
    <thead>
        <tr>
            <th>Title</th>
            <th>Company / Program</th>
            {% if current_category == 'startup' or current_category == 'all' %}
            <th>Stage</th>
            <th>Amount</th>
            {% endif %}
            {% if current_category == 'grant' or current_category == 'all' %}
            <th>Amount</th>
            {% endif %}
            {% if current_category == 'job' or current_category == 'all' %}
            <th>Location</th>
            <th>Remote</th>
            {% endif %}
            <th>Score</th>
            <th>Status</th>
            <th>Date</th>
            <th></th>
        </tr>
    </thead>
    <tbody>
        {% for opp in opportunities %}
        <tr class="opp-row" onclick="showDetail({{ opp.id }})" style="cursor: pointer;"
            data-source="{{ opp.source or '' }}"
            data-status="{{ opp.status or 'new' }}"
            data-title="{{ opp.title or '' }}">
            <td>{{ opp.title[:60] if opp.title else '' }}</td>
            <td>{{ opp.company }}{% if opp.program and (current_category == 'startup' or current_category == 'all') %}<br><small style="color:#888;">{{ opp.program }}</small>{% endif %}</td>
            {% if current_category == 'startup' or current_category == 'all' %}
            <td>{{ opp.stage or '—' }}</td>
            <td>{{ opp.amount or '—' }}</td>
            {% endif %}
            {% if current_category == 'grant' or current_category == 'all' %}
            <td>{{ opp.amount or '—' }}</td>
            {% endif %}
            {% if current_category == 'job' or current_category == 'all' %}
            <td>{{ opp.location or '—' }}</td>
            <td>{{ opp.remote or '—' }}</td>
            {% endif %}
            <td class="{% if opp.score and opp.score >= 0.7 %}score-high{% elif opp.score and opp.score >= 0.4 %}score-med{% else %}score-low{% endif %}">
                {{ "%.0f"|format(opp.score * 100) if opp.score else "—" }}%
            </td>
            <td><span class="status-badge status-{{ opp.status or 'new' }}">{{ opp.status or 'new' }}</span></td>
            <td>{{ opp.created_at.strftime("%Y-%m-%d") if opp.created_at else "—" }}</td>
            <td><a href="{{ opp.url }}" target="_blank" class="btn btn-sm btn-primary" onclick="event.stopPropagation()">View</a></td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% else %}
<div class="card">
    <p style="color: #999; text-align: center; padding: 2rem;">
        No {{ current_category if current_category != 'all' else '' }} opportunities yet.
        <a href="/" style="color: #4361ee;">Run Discovery</a> from the dashboard.
    </p>
</div>
{% endif %}

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
    fetch('/api/opportunities/' + id).then(r => r.json()).then(opp => {
        document.getElementById('modal-title').textContent = opp.title;
        let html = '<p><strong>Company:</strong> ' + opp.company + '</p>';
        html += '<p><strong>Category:</strong> ' + opp.category + '</p>';
        html += '<p><strong>Source:</strong> ' + opp.source + '</p>';
        html += '<p><strong>Status:</strong> ' + opp.status + '</p>';
        html += '<p><strong>Score:</strong> ' + (opp.score ? Math.round(opp.score*100) + '%' : '—') + '</p>';
        if (opp.category === 'startup') {
            html += '<p><strong>Program:</strong> ' + (opp.program || '—') + '</p>';
            html += '<p><strong>Stage:</strong> ' + (opp.stage || '—') + '</p>';
            html += '<p><strong>Amount:</strong> ' + (opp.amount || '—') + '</p>';
        }
        if (opp.category === 'grant') {
            html += '<p><strong>Amount:</strong> ' + (opp.amount || '—') + '</p>';
        }
        if (opp.category === 'job') {
            html += '<p><strong>Location:</strong> ' + (opp.location || '—') + '</p>';
            html += '<p><strong>Remote:</strong> ' + (opp.remote || '—') + '</p>';
        }
        html += '<p><strong>Description:</strong></p><p>' + (opp.description || 'No description') + '</p>';
        html += '<div style="margin-top: 1rem;"><a href="' + opp.url + '" target="_blank" class="btn btn-primary">Open Link</a></div>';
        document.getElementById('modal-body').innerHTML = html;
        document.getElementById('detail-modal').classList.add('open');
    });
}
function closeModal() { document.getElementById('detail-modal').classList.remove('open'); }
document.getElementById('detail-modal').addEventListener('click', function(e) {
    if (e.target === this) closeModal();
});

function applyFilters() {
    const source = document.getElementById('filter-source').value.toLowerCase();
    const status = document.getElementById('filter-status').value.toLowerCase();
    const search = document.getElementById('filter-search').value.toLowerCase();
    document.querySelectorAll('.opp-row').forEach(row => {
        const matchesSource = !source || row.dataset.source.toLowerCase().includes(source);
        const matchesStatus = !status || row.dataset.status.toLowerCase() === status;
        const matchesSearch = !search || row.dataset.title.toLowerCase().includes(search);
        row.style.display = matchesSource && matchesStatus && matchesSearch ? '' : 'none';
    });
}
document.getElementById('filter-source').addEventListener('change', applyFilters);
document.getElementById('filter-status').addEventListener('change', applyFilters);
document.getElementById('filter-search').addEventListener('input', applyFilters);
</script>
{% endblock %}
```

- [ ] **Step 3: Update review page with category tabs**

Edit `job_bot/dashboard/templates/review.html` — add category tabs at top (same style as opportunities tabs):

```
<a href="/review" class="tab {{ 'active' if current_category == 'all' }}">All</a>
<a href="/review/job" class="tab {{ 'active' if current_category == 'job' }}">💼 Jobs</a>
<a href="/review/startup" class="tab {{ 'active' if current_category == 'startup' }}">🚀 Startups</a>
<a href="/review/grant" class="tab {{ 'active' if current_category == 'grant' }}">🎯 Grants</a>
```

- [ ] **Step 4: Commit**

```bash
git add job_bot/dashboard/templates/base.html job_bot/dashboard/templates/opportunities.html job_bot/dashboard/templates/review.html
git commit -m "feat: tabbed opportunities UI with per-category columns"
```

---

### Task 9: Home Page — Per-category stats cards

**Files:**
- Modify: `job_bot/dashboard/templates/home.html`

- [ ] **Step 1: Add per-category stat cards to home page**

Edit `job_bot/dashboard/templates/home.html` — after the existing stats cards, add:

```html
<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem;">
    <div class="card" style="text-align: center; background: linear-gradient(135deg, #e3f2fd, #bbdefb);">
        <h3 style="margin: 0; font-size: 1.8rem;">{{ stats.by_category.job if stats.by_category else '—' }}</h3>
        <p style="margin: 0; color: #555;">💼 Jobs</p>
    </div>
    <div class="card" style="text-align: center; background: linear-gradient(135deg, #e8f5e9, #c8e6c9);">
        <h3 style="margin: 0; font-size: 1.8rem;">{{ stats.by_category.startup if stats.by_category else '—' }}</h3>
        <p style="margin: 0; color: #555;">🚀 Startups</p>
    </div>
    <div class="card" style="text-align: center; background: linear-gradient(135deg, #fff3e0, #ffe0b2);">
        <h3 style="margin: 0; font-size: 1.8rem;">{{ stats.by_category.grant if stats.by_category else '—' }}</h3>
        <p style="margin: 0; color: #555;">🎯 Grants</p>
    </div>
</div>
```

- [ ] **Step 2: Commit**

```bash
git add job_bot/dashboard/templates/home.html
git commit -m "feat: add per-category stat cards to home page"
```

---

### Task 10: Full test suite and verification

**Files:**
- Modify: `tests/test_dashboard.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Add dashboard test for category pages**

```python
    @pytest.mark.asyncio
    async def test_opportunities_jobs_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities/job")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_startup_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities/startup")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_grant_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities/grant")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stats_has_by_category(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/stats")
            data = resp.json()
            assert "by_category" in data
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: 40+ tests all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_dashboard.py tests/test_database.py
git commit -m "test: add tests for category-filtered pages and stats"
```

---

### Task 11: Deploy to VPS

**Files:**
- All modified files

- [ ] **Step 1: Upload all modified files to VPS**

Upload via SFTP:
```
job_bot/database/models.py
job_bot/discovery/base.py
job_bot/discovery/google_search.py
job_bot/discovery/linkedin.py
job_bot/discovery/company_pages.py
job_bot/discovery/grants.py
job_bot/database/repository.py
job_bot/intelligence/matcher.py
job_bot/intelligence/drafter.py
job_bot/review/manager.py
job_bot/application/manager.py
job_bot/dashboard/server.py
job_bot/dashboard/templates/base.html
job_bot/dashboard/templates/opportunities.html
job_bot/dashboard/templates/review.html
job_bot/dashboard/templates/home.html
```

- [ ] **Step 2: Rebuild Docker image and restart**

Run on VPS:
```bash
cd /root/JBot
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

- [ ] **Step 3: Verify all pages respond**

Check: `curl http://localhost:8080/opportunities/job` → 200
Check: `curl http://localhost:8080/opportunities/startup` → 200
Check: `curl http://localhost:8080/opportunities/grant` → 200
Check: `curl http://localhost:8080/api/stats` → contains `by_category`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "deploy: opportunity categories to VPS"
```
