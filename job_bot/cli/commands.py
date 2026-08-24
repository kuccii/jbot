import asyncio
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
    from job_bot.discovery.orchestrator import DiscoveryOrchestrator
    orch = DiscoveryOrchestrator(repo, cfg.discovery.model_dump(), web_services=cfg.web_services.model_dump())
    results = asyncio.run(orch.run_all())
    typer.echo(f"Discovery complete. Found {len(results)} new opportunities.")


@app.command()
def schedule():
    """Start the discovery scheduler."""
    cfg, repo = _init()
    from job_bot.discovery.orchestrator import DiscoveryOrchestrator
    from job_bot.discovery.scheduler import start_scheduler
    orch = DiscoveryOrchestrator(repo, cfg.discovery.model_dump(), web_services=cfg.web_services.model_dump())
    start_scheduler(orch, cfg.discovery.interval_hours)
    typer.echo(f"Scheduler started (every {cfg.discovery.interval_hours}h). Press Ctrl+C to stop.")


@app.command()
def review():
    """Review pending matches with AI scores and drafts."""
    cfg, repo = _init()
    from job_bot.pipeline import Pipeline
    pipeline = Pipeline(cfg, repo)
    results = asyncio.run(pipeline.review())
    if results:
        for r in results:
            typer.echo(f"\n[{r['opportunity_id']}] {r['title']} @ {r['company']} (Score: {r['score']:.2f})")
            typer.echo(f"  Cover: {r['cover_letter'][:100]}...")
    else:
        typer.echo("No pending reviews.")


@app.command()
def apply(opportunity_id: int = typer.Argument(..., help="Opportunity ID")):
    """Submit application for an opportunity."""
    cfg, repo = _init()
    opps = repo.get_pending_opportunities()
    matched = [o for o in opps if o.id == opportunity_id]
    if not matched:
        typer.echo(f"Opportunity #{opportunity_id} not found or already processed.")
        return
    opp = matched[0]
    from job_bot.pipeline import Pipeline
    pipeline = Pipeline(cfg, repo)
    result = asyncio.run(pipeline.apply(opp.url))
    typer.echo(f"Result: {result}")


@app.command()
def run():
    """Run full cycle: discover -> review -> apply."""
    cfg, repo = _init()
    from job_bot.pipeline import Pipeline
    pipeline = Pipeline(cfg, repo)
    result = asyncio.run(pipeline.run_full_cycle())
    typer.echo(f"Done. Discovered: {result['discovered']}, Reviewed: {result['reviews']}, Applied: {result['applied']}")


@app.command()
def notify(message: str = typer.Argument("Test message from Job Bot", help="Message to send")):
    """Send a WhatsApp test message."""
    cfg = load_config()
    if not cfg.notifications.whatsapp.enabled:
        typer.echo("WhatsApp is not enabled in config.")
        return
    from job_bot.notifications.whatsapp import WhatsAppNotifier
    notifier = WhatsAppNotifier(
        cfg.notifications.whatsapp.phone_number_id,
        cfg.notifications.whatsapp.token,
    )
    result = asyncio.run(notifier.send_message(cfg.notifications.whatsapp.recipient, message))
    typer.echo(f"Message sent: {result}")


@app.command()
def status():
    """Show application tracking dashboard."""
    cfg, repo = _init()
    stats = repo.get_stats()
    typer.echo(f"Total: {stats['total']}")
    typer.echo(f"New: {stats['new']}")
    typer.echo(f"Applied: {stats['applied']}")
    typer.echo(f"Rejected: {stats.get('rejected', 0)}")
    typer.echo(f"Dead: {stats.get('dead', 0)}")


@app.command()
def dashboard(host: str = "127.0.0.1", port: int = 8080):
    """Launch the web dashboard."""
    from job_bot.dashboard.server import run_server
    typer.echo(f"Dashboard starting at http://{host}:{port}")
    run_server(host=host, port=port)


@app.command()
def config():
    """Show current configuration."""
    cfg = load_config()
    typer.echo(cfg.model_dump_json(indent=2))


@app.command()
def import_cv(cv_path: str = typer.Argument(..., help="Path to CV file (txt)")):
    """Import CV and extract text for profile."""
    from job_bot.profile.cv_parser import extract_text
    from job_bot.profile.models import UserProfile
    from job_bot.profile.repository import ProfileRepository
    text = extract_text(cv_path)
    cfg = load_config()
    profile_repo = ProfileRepository(cfg.database.path)
    profile = profile_repo.load() or UserProfile()
    profile.cv_text = text
    profile.cv_path = cv_path
    profile_repo.save(profile)
    typer.echo(f"Imported CV ({len(text)} chars)")


@app.command()
def profile():
    """Show configured profile."""
    cfg = load_config()
    from job_bot.profile.repository import ProfileRepository
    profile_repo = ProfileRepository(cfg.database.path)
    p = profile_repo.load()
    if p:
        typer.echo(f"Name: {p.name}")
        typer.echo(f"Email: {p.email}")
        typer.echo(f"Bio: {p.bio[:100]}..." if len(p.bio) > 100 else f"Bio: {p.bio}")
        typer.echo(f"Skills: {', '.join(p.skills)}")
        typer.echo(f"CV: {len(p.cv_text)} chars loaded")
    else:
        typer.echo("No profile configured. Use 'job-bot import-cv <path>' to add your CV.")


@app.command()
def purge(
    what: str = typer.Argument(..., help="What to purge: dead, old, source, unscored, duplicates, all"),
    days: int = typer.Option(30, help="Days threshold for 'old' purge"),
    source: str = typer.Option("", help="Source name for 'source' purge"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Purge opportunities from the database."""
    cfg, repo = _init()

    descriptions = {
        "dead": "Remove all dead opportunities",
        "old": f"Remove opportunities older than {days} days (not applied)",
        "source": f"Remove all opportunities from source '{source}'",
        "unscored": "Remove all unscored new opportunities",
        "duplicates": "Remove duplicate opportunities (keep newest)",
        "all": "Remove ALL opportunities (nuclear option)",
    }

    if what not in descriptions:
        typer.echo(f"Unknown purge type: {what}")
        typer.echo(f"Available: {', '.join(descriptions.keys())}")
        return

    desc = descriptions[what]
    typer.echo(f"Purge: {desc}")

    if not force:
        if not typer.confirm("Are you sure?"):
            typer.echo("Cancelled.")
            return

    before = repo.get_stats()["total"]

    if what == "dead":
        removed = repo.purge_dead()
    elif what == "old":
        removed = repo.purge_old(days)
    elif what == "source":
        if not source:
            typer.echo("Error: --source is required for 'source' purge")
            return
        removed = repo.purge_by_source(source)
    elif what == "unscored":
        removed = repo.purge_unscored()
    elif what == "duplicates":
        removed = repo.purge_duplicates()
    elif what == "all":
        removed = repo.purge_all()

    after = repo.get_stats()["total"]
    typer.echo(f"Purged {removed} opportunities. ({before} -> {after})")
