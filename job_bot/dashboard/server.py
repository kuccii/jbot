import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from job_bot.config import load_config
from job_bot.database.repository import init_db, Repository
from job_bot.database.models import Opportunity
from job_bot.pipeline import Pipeline

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Job Bot Dashboard")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_last_run = {"discovery": None, "review": None, "status": "idle"}


def get_repo() -> Repository:
    cfg = load_config()
    db_url = init_db(cfg.database.path)
    return Repository(db_url)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    repo = get_repo()
    stats = repo.get_stats()
    stats["by_category"] = repo.get_stats_by_category()
    logs = repo.get_audit_logs(limit=20)
    return templates.TemplateResponse(request, "home.html", {
        "stats": stats, "activity": logs, "page": "home", "last_run": _last_run,
    })


@app.post("/api/discover")
async def api_discover():
    cfg = load_config()
    repo = get_repo()
    pipeline = Pipeline(cfg, repo)
    _last_run["discovery"] = "running"
    _last_run["status"] = "running"
    asyncio.create_task(_run_discovery(pipeline, repo))
    return {"status": "started"}


@app.post("/api/review")
async def api_review():
    cfg = load_config()
    repo = get_repo()
    pipeline = Pipeline(cfg, repo)
    _last_run["review"] = "running"
    _last_run["status"] = "running"
    asyncio.create_task(_run_review(pipeline, repo))
    return {"status": "started"}


async def _run_discovery(pipeline: Pipeline, repo: Repository):
    global _last_run
    try:
        results = await pipeline.discover()
        _last_run["discovery"] = f"Found {len(results)} opportunities"
        _last_run["status"] = "idle"
        repo.log_audit("discovery_complete", "pipeline", {"count": len(results)})
    except Exception as e:
        _last_run["discovery"] = f"Error: {e}"
        _last_run["status"] = "idle"
        repo.log_audit("discovery_error", "pipeline", {"error": str(e)})


async def _run_review(pipeline: Pipeline, repo: Repository):
    global _last_run
    try:
        reviews = await pipeline.review()
        _last_run["review"] = f"Reviewed {len(reviews)} opportunities"
        _last_run["status"] = "idle"
        repo.log_audit("review_complete", "pipeline", {"count": len(reviews)})
    except Exception as e:
        _last_run["review"] = f"Error: {e}"
        _last_run["status"] = "idle"
        repo.log_audit("review_error", "pipeline", {"error": str(e)})


@app.get("/api/stats")
async def api_stats():
    repo = get_repo()
    stats = repo.get_stats()
    stats["rejected"] = stats.get("rejected", 0)
    stats["by_category"] = repo.get_stats_by_category()
    return stats


@app.get("/api/status")
async def api_status():
    return _last_run


@app.get("/api/activity")
async def api_activity():
    repo = get_repo()
    logs = repo.get_audit_logs(limit=20)
    return [{"action": l.action, "component": l.component, "created_at": str(l.created_at)} for l in logs]


@app.get("/api/stats/daily")
async def daily_stats():
    repo = get_repo()
    return repo.get_daily_trend(days=14)


@app.get("/opportunities", response_class=HTMLResponse)
@app.get("/opportunities/{category:path}", response_class=HTMLResponse)
async def opportunities_page(request: Request, category: str = "all"):
    repo = get_repo()
    sources = []
    with repo.engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text("SELECT DISTINCT source FROM opportunities WHERE source IS NOT NULL"))
        sources = [row[0] for row in result if row[0]]
    with Session(repo.engine) as session:
        query = session.query(Opportunity)
        if category in ("job", "startup", "grant"):
            query = query.filter(Opportunity.category == category)
        opps = query.order_by(Opportunity.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(request, "opportunities.html", {
        "opportunities": opps, "sources": sources, "page": "opportunities",
        "current_category": category,
    })


@app.get("/api/opportunities/{opp_id}")
async def opportunity_detail(opp_id: int):
    repo = get_repo()
    with Session(repo.engine) as session:
        opp = session.query(Opportunity).filter_by(id=opp_id).first()
        if not opp:
            return {"error": "not found"}
        return {
            "id": opp.id, "title": opp.title, "company": opp.company,
            "url": opp.url, "source": opp.source, "status": opp.status,
            "score": opp.score, "location": opp.location, "remote": opp.remote,
            "description": opp.description, "salary_range": opp.salary_range,
            "category": opp.category, "program": opp.program,
            "stage": opp.stage, "amount": opp.amount,
        }


@app.get("/review", response_class=HTMLResponse)
@app.get("/review/{category:path}", response_class=HTMLResponse)
async def review_page(request: Request, category: str = "all"):
    repo = get_repo()
    if category in ("job", "startup", "grant"):
        pending = repo.get_pending_opportunities(min_score=0.3, category=category)
    else:
        pending = repo.get_pending_opportunities(min_score=0.3)
    reviews = []
    for opp in pending:
        reviews.append({
            "id": opp.id, "title": opp.title, "company": opp.company,
            "source": opp.source, "score": opp.score or 0.5, "category": opp.category,
            "cover_letter": f"Dear {opp.company} team,\n\nI am excited to apply for {opp.title} at {opp.company}. With my background in {', '.join(load_config().profile.skills) if load_config().profile.skills else 'relevant skills'}, I believe I would be a strong addition to your team.\n\nBest regards,\n{load_config().profile.name or 'Applicant'}",
        })
    return templates.TemplateResponse(request, "review.html", {
        "reviews": reviews, "page": "review", "current_category": category,
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


@app.get("/applications", response_class=HTMLResponse)
async def applications_page(request: Request):
    repo = get_repo()
    from job_bot.database.models import Application
    app_list = []
    with Session(repo.engine) as session:
        apps = session.query(Application).order_by(Application.created_at.desc()).limit(50).all()
        for a in apps:
            opp = session.query(Opportunity).filter_by(id=a.opportunity_id).first()
            app_list.append({
                "id": a.id, "company": opp.company if opp else "—",
                "role": opp.title if opp else "—", "platform": a.platform,
                "status": a.status, "submitted_at": str(a.submitted_at or ""),
            })
    return templates.TemplateResponse(request, "applications.html", {
        "applications": app_list, "page": "applications",
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    cfg = load_config()
    config_text = Path.cwd().joinpath("config.yaml").read_text(encoding="utf-8") if Path.cwd().joinpath("config.yaml").exists() else ""
    return templates.TemplateResponse(request, "settings.html", {
        "config": cfg, "page": "settings", "config_text": config_text,
        "has_gemini_key": bool(cfg.llm.gemini_api_key),
        "has_nim_key": bool(cfg.llm.nim_api_key),
        "has_opencode_key": bool(cfg.llm.opencode_api_key),
        "has_serper_key": bool(cfg.discovery.serper_api_key),
        "has_whatsapp_token": bool(cfg.notifications.whatsapp.token),
    })


@app.post("/settings")
async def save_settings(request: Request):
    cfg = load_config()
    form = await request.form()
    cfg.profile.name = form.get("name", "")
    cfg.profile.email = form.get("email", "")
    cfg.profile.phone = form.get("phone", "")
    cfg.profile.skills = [s.strip() for s in form.get("skills", "").split(",") if s.strip()]
    cfg.llm.provider = form.get("llm_provider", "ollama")
    cfg.llm.model = form.get("llm_model", "llama3.1:8b")
    cfg.llm.embedding_model = form.get("embedding_model", "nomic-embed-text")
    cfg.llm.temperature = float(form.get("temperature", 0.3))
    cfg.llm.ollama_base_url = form.get("ollama_base_url", "http://localhost:11434")
    gemini_key = form.get("gemini_api_key", "")
    if gemini_key:
        cfg.llm.gemini_api_key = gemini_key
    nim_key = form.get("nim_api_key", "")
    if nim_key:
        cfg.llm.nim_api_key = nim_key
    opencode_key = form.get("opencode_api_key", "")
    if opencode_key:
        cfg.llm.opencode_api_key = opencode_key
    cfg.llm.opencode_base_url = form.get("opencode_base_url", "https://opencode.ai/zen/v1")
    serper_key = form.get("serper_api_key", "")
    if serper_key:
        cfg.discovery.serper_api_key = serper_key
    cfg.discovery.grants_keywords = [k.strip() for k in form.get("grants_keywords", "").split(",") if k.strip()]
    cfg.discovery.companies = [c.strip() for c in form.get("companies", "").split("\n") if c.strip()]
    cfg.discovery.sources["google_search"] = form.get("source_google_search") == "on"
    cfg.discovery.sources["linkedin"] = form.get("source_linkedin") == "on"
    cfg.discovery.sources["grants"] = form.get("source_grants") == "on"
    cfg.discovery.sources["ycombinator"] = form.get("source_ycombinator") == "on"
    cfg.discovery.sources["accelerators"] = form.get("source_accelerators") == "on"
    cfg.discovery.sources["fellowships"] = form.get("source_fellowships") == "on"
    cfg.discovery.sources["hackathons"] = form.get("source_hackathons") == "on"
    cfg.discovery.sources["african_jobs"] = form.get("source_african_jobs") == "on"
    cfg.application.human_approval = form.get("human_approval") == "on"
    cfg.application.max_applications_per_run = int(form.get("max_applications_per_run", 5))
    cfg.notifications.whatsapp.enabled = form.get("whatsapp_enabled") == "on"
    cfg.notifications.whatsapp.phone_number_id = form.get("whatsapp_phone_number_id", "")
    whatsapp_token = form.get("whatsapp_token", "")
    if whatsapp_token:
        cfg.notifications.whatsapp.token = whatsapp_token
    cfg.notifications.whatsapp.recipient = form.get("whatsapp_recipient", "")
    import yaml
    with open(Path.cwd() / "config.yaml", "w") as f:
        yaml.dump(cfg.model_dump(), f, default_flow_style=False)
    repo = get_repo()
    repo.log_audit("settings_updated", "dashboard", {})
    config_text = Path.cwd().joinpath("config.yaml").read_text(encoding="utf-8")
    return templates.TemplateResponse(request, "settings.html", {
        "config": cfg, "page": "settings", "saved": True, "config_text": config_text,
        "has_gemini_key": bool(cfg.llm.gemini_api_key),
        "has_nim_key": bool(cfg.llm.nim_api_key),
        "has_opencode_key": bool(cfg.llm.opencode_api_key),
        "has_serper_key": bool(cfg.discovery.serper_api_key),
        "has_whatsapp_token": bool(cfg.notifications.whatsapp.token),
    })


def run_server(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
