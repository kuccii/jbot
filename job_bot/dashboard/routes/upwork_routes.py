"""Upwork management routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from job_bot.config import load_config
from job_bot.dashboard.routes._deps import get_repo

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/upwork", response_class=HTMLResponse)
async def upwork_main(request: Request):
    cfg = load_config()
    return templates.TemplateResponse(request, "upwork.html", {
        "page": "upwork",
    })


@router.get("/upwork/jobs", response_class=HTMLResponse)
async def upwork_jobs(request: Request):
    repo = get_repo()
    from sqlalchemy import text
    with repo.engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, title, company, url, status, client_company, client_website, created_at FROM opportunities WHERE source='upwork' ORDER BY created_at DESC LIMIT 100")
        )
        opps = [dict(row._mapping) for row in result]
    return templates.TemplateResponse(request, "upwork_jobs.html", {
        "opportunities": opps, "page": "upwork",
    })


@router.get("/upwork/settings", response_class=HTMLResponse)
async def upwork_settings(request: Request):
    cfg = load_config()
    has_api = bool(cfg.upwork.client_id and cfg.upwork.client_secret and (cfg.upwork.access_token or cfg.upwork.refresh_token))
    return templates.TemplateResponse(request, "upwork_settings.html", {
        "keywords": cfg.upwork.keywords, "page": "upwork", "saved": False,
        "has_api_credentials": has_api,
    })


@router.post("/upwork/settings")
async def upwork_save_settings(request: Request):
    cfg = load_config()
    form = await request.form()
    raw = form.get("keywords", "")
    cfg.upwork.keywords = [k.strip() for k in raw.split(",") if k.strip()]
    import yaml
    with open(Path.cwd() / "config.yaml", "w") as f:
        yaml.dump(cfg.model_dump(), f, default_flow_style=False)
    return templates.TemplateResponse(request, "upwork_settings.html", {
        "keywords": cfg.upwork.keywords, "page": "upwork", "saved": True,
    })


@router.post("/api/upwork/discover")
async def upwork_discover():
    cfg = load_config()
    from job_bot.discovery.base import SearchCriteria
    from job_bot.discovery.registry import get_scraper
    repo = get_repo()
    scraper = get_scraper("upwork")
    criteria = SearchCriteria(keywords=cfg.upwork.keywords)
    opps = await scraper.discover(criteria)
    count = 0
    for opp in opps:
        oid = repo.add_opportunity({
            "title": opp.title, "company": opp.company, "url": opp.url,
            "description": opp.description, "source": opp.source,
            "category": opp.category, "remote": opp.remote, "deadline": opp.deadline,
            "salary_range": opp.salary_range, "client_company": opp.client_company,
        })
        if oid:
            count += 1
    return {"count": count}
