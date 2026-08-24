"""Opportunities listing routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from job_bot.database.models import Opportunity
from job_bot.dashboard.routes._deps import get_repo

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

CATEGORY_LABELS = {
    "job": "Jobs",
    "startup": "Startups",
    "grant": "Grants",
}


def _list_opportunities(category: str | None = None) -> tuple[list, list]:
    repo = get_repo()
    sources = []
    with repo.engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text("SELECT DISTINCT source FROM opportunities WHERE source IS NOT NULL"))
        sources = [row[0] for row in result if row[0]]
    with Session(repo.engine) as session:
        query = session.query(Opportunity)
        if category:
            query = query.filter(Opportunity.category == category)
        opps = query.order_by(Opportunity.created_at.desc()).all()
    return opps, sources


@router.get("/opportunities", response_class=HTMLResponse)
async def opportunities_page(request: Request):
    opps, sources = _list_opportunities()
    return templates.TemplateResponse(request, "opportunities.html", {
        "opportunities": opps, "sources": sources, "page": "opportunities",
        "category": "job", "category_label": CATEGORY_LABELS["job"],
    })


@router.get("/opportunities/{category}", response_class=HTMLResponse)
async def opportunities_category_page(request: Request, category: str):
    if category not in CATEGORY_LABELS:
        return templates.TemplateResponse(request, "opportunities.html", {
            "opportunities": [], "sources": [], "page": "opportunities",
            "category": "job", "category_label": CATEGORY_LABELS["job"],
        })
    opps, sources = _list_opportunities(category)
    return templates.TemplateResponse(request, "opportunities.html", {
        "opportunities": opps, "sources": sources, "page": "opportunities",
        "category": category, "category_label": CATEGORY_LABELS[category],
    })


@router.get("/api/opportunities/{opp_id}")
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
            "category": opp.category, "program": opp.program, "stage": opp.stage,
            "amount": opp.amount, "deadline": opp.deadline.isoformat() if opp.deadline else None,
        }
