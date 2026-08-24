"""Review queue routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from job_bot.config import load_config
from job_bot.dashboard.routes._deps import get_repo

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/review", response_class=HTMLResponse)
async def review_page(request: Request, category: str = "all", sort: str = "score_desc"):
    return _render_review(request, category, sort)


@router.get("/review/{category}", response_class=HTMLResponse)
async def review_category_page(request: Request, category: str, sort: str = "score_desc"):
    return _render_review(request, category, sort)


def _render_review(request: Request, category: str, sort: str):
    repo = get_repo()
    cfg = load_config()
    if category not in ("all", "job", "startup", "grant"):
        category = "all"
    pending = repo.get_pending_opportunities_sorted(
        min_score=0.3, category=category if category != "all" else None, sort_by=sort,
    )
    reviews = []
    for opp in pending:
        cover = getattr(opp, '_cover_letter', None) or (
            f"Dear {opp.company} team,\n\nI am excited to apply for {opp.title} at {opp.company}."
            f" With my background in {', '.join(cfg.profile.skills) if cfg.profile.skills else 'relevant skills'},"
            f" I believe I would be a strong addition to your team.\n\nBest regards,\n{cfg.profile.name or 'Applicant'}"
        )
        reviews.append({
            "id": opp.id, "title": opp.title, "company": opp.company,
            "source": opp.source, "score": opp.score or 0.5,
            "liveness_status": opp.liveness_status or "unknown",
            "prose": opp.score_prose or "",
            "scores": {
                "cv_match": opp.score_cv_match,
                "compensation": opp.score_compensation,
                "culture": opp.score_culture,
                "red_flags": opp.score_red_flags,
                "legitimacy": opp.score_legitimacy,
                "global": opp.score_global,
            },
            "cover_letter": cover,
        })
    return templates.TemplateResponse(request, "review.html", {
        "reviews": reviews, "page": "review", "sort": sort, "category": category,
    })


@router.post("/api/review/{opp_id}/approve")
async def approve_opportunity(opp_id: int, data: dict = None):
    repo = get_repo()
    repo.update_opportunity_status(opp_id, "applied")
    repo.log_audit("approved", "review", {"opportunity_id": opp_id})
    return {"success": True}


@router.post("/api/review/{opp_id}/skip")
async def skip_opportunity(opp_id: int):
    repo = get_repo()
    repo.update_opportunity_status(opp_id, "evaluated")
    repo.log_audit("skipped", "review", {"opportunity_id": opp_id})
    return {"success": True}


@router.post("/api/review/batch-reject")
async def batch_reject():
    repo = get_repo()
    count = 0
    for opp in repo.get_pending_opportunities(min_score=0.3):
        if opp.liveness_status == "dead":
            repo.update_opportunity_status(opp.id, "rejected")
            count += 1
    return {"success": True, "count": count}


@router.post("/api/review/{opp_id}/reject")
async def reject_opportunity(opp_id: int):
    repo = get_repo()
    repo.update_opportunity_status(opp_id, "rejected")
    repo.log_audit("rejected", "review", {"opportunity_id": opp_id})
    return {"success": True}
