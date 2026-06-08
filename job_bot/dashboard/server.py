from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from job_bot.config import load_config
from job_bot.database.repository import init_db, Repository
from job_bot.database.models import Opportunity

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
    return templates.TemplateResponse(request, "home.html", {
        "stats": stats,
        "activity": [],
        "page": "home",
    })


@app.get("/api/stats/daily")
async def daily_stats():
    labels = []
    values = []
    from datetime import datetime, timedelta
    for i in range(13, -1, -1):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(date)
        values.append(0)
    return {"labels": labels, "values": values}


@app.get("/opportunities", response_class=HTMLResponse)
async def opportunities_page(request: Request):
    repo = get_repo()
    sources = []
    with repo.engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text("SELECT DISTINCT source FROM opportunities WHERE source IS NOT NULL"))
        sources = [row[0] for row in result if row[0]]
    with Session(repo.engine) as session:
        opps = session.query(Opportunity).order_by(Opportunity.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(request, "opportunities.html", {
        "opportunities": opps, "sources": sources, "page": "opportunities",
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
        }


@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    repo = get_repo()
    pending = repo.get_pending_opportunities(min_score=0.3)
    reviews = []
    for opp in pending:
        reviews.append({
            "id": opp.id, "title": opp.title, "company": opp.company,
            "source": opp.source, "score": opp.score or 0.5,
            "cover_letter": f"Dear {opp.company} team,\n\nI am excited to apply for {opp.title} at {opp.company}. With my background in {', '.join(load_config().profile.skills) if load_config().profile.skills else 'relevant skills'}, I believe I would be a strong addition to your team.\n\nBest regards,\n{load_config().profile.name or 'Applicant'}",
        })
    return templates.TemplateResponse(request, "review.html", {
        "reviews": reviews, "page": "review",
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
    return templates.TemplateResponse(request, "settings.html", {
        "config": cfg, "page": "settings",
    })


@app.post("/settings")
async def save_settings(request: Request):
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
    with open(Path.cwd() / "config.yaml", "w") as f:
        yaml.dump(cfg.model_dump(), f, default_flow_style=False)
    repo = get_repo()
    repo.log_audit("settings_updated", "dashboard", {})
    return templates.TemplateResponse(request, "settings.html", {
        "config": cfg, "page": "settings", "saved": True,
    })


def run_server(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
