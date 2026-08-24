"""Home dashboard routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from job_bot.dashboard.routes._deps import get_repo, _last_run

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    repo = get_repo()
    stats = repo.get_stats()
    logs = repo.get_audit_logs(limit=20)
    return templates.TemplateResponse(request, "home.html", {
        "stats": stats, "activity": logs, "page": "home", "last_run": _last_run,
    })


@router.get("/api/stats")
async def api_stats():
    repo = get_repo()
    stats = repo.get_stats()
    stats["by_category"] = repo.get_stats_by_category()
    return stats


@router.get("/api/status")
async def api_status():
    return _last_run


@router.get("/api/activity")
async def api_activity():
    repo = get_repo()
    logs = repo.get_audit_logs(limit=20)
    return [{"action": l.action, "component": l.component, "created_at": str(l.created_at)} for l in logs]


@router.get("/api/stats/daily")
async def daily_stats():
    repo = get_repo()
    return repo.get_daily_trend(days=14)


@router.post("/api/purge/dead")
async def purge_dead():
    repo = get_repo()
    count = repo.purge_dead()
    repo.log_audit("purge_dead", "dashboard", {"removed": count})
    return {"success": True, "removed": count}


@router.post("/api/purge/old")
async def purge_old():
    repo = get_repo()
    count = repo.purge_old(days=30)
    repo.log_audit("purge_old", "dashboard", {"removed": count})
    return {"success": True, "removed": count}


@router.post("/api/purge/unscored")
async def purge_unscored():
    repo = get_repo()
    count = repo.purge_unscored()
    repo.log_audit("purge_unscored", "dashboard", {"removed": count})
    return {"success": True, "removed": count}


@router.post("/api/purge/duplicates")
async def purge_duplicates():
    repo = get_repo()
    count = repo.purge_duplicates()
    repo.log_audit("purge_duplicates", "dashboard", {"removed": count})
    return {"success": True, "removed": count}
