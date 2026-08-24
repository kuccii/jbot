"""API routes for triggering discovery and review."""

import asyncio

from fastapi import APIRouter

from job_bot.config import load_config
from job_bot.pipeline import Pipeline
from job_bot.utils.logging import get_logger
from job_bot.dashboard.routes._deps import get_repo, _last_run

router = APIRouter()
logger = get_logger()


@router.post("/api/discover")
async def api_discover():
    cfg = load_config()
    repo = get_repo()
    pipeline = Pipeline(cfg, repo)
    _last_run["discovery"] = "running"
    _last_run["status"] = "running"
    asyncio.create_task(_run_discovery(pipeline, repo))
    return {"status": "started"}


@router.post("/api/review")
async def api_review():
    cfg = load_config()
    repo = get_repo()
    pipeline = Pipeline(cfg, repo)
    _last_run["review"] = "running"
    _last_run["status"] = "running"
    asyncio.create_task(_run_review(pipeline, repo))
    return {"status": "started"}


async def _run_discovery(pipeline: Pipeline, repo):
    global _last_run
    try:
        results = await pipeline.discover()
        _last_run["discovery"] = f"Found {len(results)} opportunities"

        # Auto-run review/scoring after discovery
        try:
            reviews = await pipeline.review()
            _last_run["review"] = f"Reviewed {len(reviews)} opportunities"
            repo.log_audit("auto_review_complete", "pipeline", {"count": len(reviews)})
        except Exception as e2:
            logger.error("auto_review_error", error=str(e2))
            _last_run["review"] = f"Error: {e2}"

        _last_run["status"] = "idle"
        repo.log_audit("discovery_complete", "pipeline", {"count": len(results), "auto_reviewed": True})
    except Exception as e:
        _last_run["discovery"] = f"Error: {e}"
        _last_run["status"] = "idle"
        repo.log_audit("discovery_error", "pipeline", {"error": str(e)})


async def _run_review(pipeline: Pipeline, repo):
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
