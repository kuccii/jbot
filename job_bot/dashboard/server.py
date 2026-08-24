"""Job Bot Dashboard — slim app factory that mounts route modules."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from job_bot.config import load_config
from job_bot.utils.logging import get_logger
from job_bot.discovery.noise_filter import purge_noise
from job_bot.dashboard.routes import home, opportunities, review, upwork_routes, applications, settings, api

logger = get_logger()

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Job Bot Dashboard")


@app.on_event("startup")
def cleanup_noise_on_startup():
    cfg = load_config()
    stats = purge_noise(cfg.database.path, dry_run=False)
    if stats.get("removed", 0) > 0:
        logger.info("startup_noise_cleanup", removed=stats["removed"], reasons=stats.get("by_reason"))
    else:
        logger.info("startup_noise_cleanup", status="clean", checked=stats.get("total", 0))


# Mount route modules
app.include_router(home.router)
app.include_router(opportunities.router)
app.include_router(review.router)
app.include_router(upwork_routes.router)
app.include_router(applications.router)
app.include_router(settings.router)
app.include_router(api.router)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def run_server(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
