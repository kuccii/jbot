"""Applications tracking routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from job_bot.database.models import Application, Opportunity
from job_bot.dashboard.routes._deps import get_repo

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/applications", response_class=HTMLResponse)
async def applications_page(request: Request):
    repo = get_repo()
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
