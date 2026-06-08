import typer
from pathlib import Path

from job_bot.config import load_config, Config
from job_bot.database.repository import init_db, Repository
from job_bot.utils.logging import setup_logging, get_logger

app = typer.Typer(name="job-bot", help="Automated job application bot")
logger = get_logger()


def _init() -> tuple[Config, Repository]:
    cfg = load_config()
    setup_logging()
    db_url = init_db(cfg.database.path)
    repo = Repository(db_url)
    return cfg, repo


@app.command()
def discover():
    """Run opportunity discovery now."""
    cfg, repo = _init()
    logger.info("discovery_started", sources=list(cfg.discovery.sources.keys()))
    typer.echo("Discovery run initiated. Check back for results.")


@app.command()
def review():
    """Review pending matches."""
    cfg, repo = _init()
    stats = repo.get_stats()
    typer.echo(f"Opportunities: {stats['total']} total, {stats['new']} new, {stats['applied']} applied")


@app.command()
def apply(opportunity_id: int = typer.Argument(..., help="Opportunity ID to apply to")):
    """Prepare and send an application."""
    cfg, repo = _init()
    typer.echo(f"Preparing application for opportunity #{opportunity_id}")


@app.command()
def status():
    """Show application tracking dashboard."""
    cfg, repo = _init()
    stats = repo.get_stats()
    typer.echo(f"Total: {stats['total']}")
    typer.echo(f"New: {stats['new']}")
    typer.echo(f"Applied: {stats['applied']}")
    typer.echo(f"Rejected: {stats.get('rejected', 0)}")


@app.command()
def config():
    """Show current configuration."""
    cfg = load_config()
    typer.echo(cfg.model_dump_json(indent=2))


@app.command()
def profile():
    """Show configured profile."""
    cfg, repo = _init()
    typer.echo(f"Name: {cfg.profile.name}")
    typer.echo(f"Email: {cfg.profile.email}")
    typer.echo(f"Skills: {', '.join(cfg.profile.skills)}")
