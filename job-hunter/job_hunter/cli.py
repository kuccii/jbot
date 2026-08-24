"""CLI for job-hunter.

Run from the job-hunter/ folder (or anywhere, once installed):

    job-hunter discover           # fetch jobs from enabled boards, notify
    job-hunter list                # show eligible jobs, best fit first
    job-hunter search "ai engineer"
    job-hunter details 12
    job-hunter status              # counts per board
    job-hunter mark 12 applied
    job-hunter purge hidden
    job-hunter watch --interval 3600   # discover on a loop
    job-hunter notify-test         # send a test message to configured channels
    job-hunter dashboard           # launch the web dashboard
"""

from __future__ import annotations

import sys
import time

import typer

from job_hunter.config import load_config
from job_hunter.models import Store

app = typer.Typer(name="job-hunter", help="Find jobs a Rwandan can actually get.", no_args_is_help=True)


def _store() -> Store:
    return Store(load_config().database)


def _fix_console_encoding() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@app.command()
def discover(
    notify: bool = typer.Option(
        True, "--notify/--no-notify",
        help="Send a digest of newly found jobs if notifications are configured",
    ),
):
    """Fetch jobs from all enabled boards, score, store, and (optionally) notify."""
    _fix_console_encoding()
    from job_hunter.orchestrator import notify_new_jobs, run_discover

    cfg = load_config()
    print(f"Running discovery (boards: {', '.join(n for n, e in cfg.boards.items() if e)})")
    results = run_discover(cfg)
    for r in results:
        if r["error"]:
            print(f"  [x] {r['board']}: {r['error']}")
        else:
            print(f"  [ok] {r['board']}: fetched={r['fetched']} eligible={r['eligible']} new={r['added']}")
    store = _store()
    s = store.stats()
    print(f"\nTotal stored: {s['total']}")

    if notify and cfg.notifications.enabled:
        notify_results = notify_new_jobs(cfg)
        if notify_results:
            print("\nNotifications:")
            for channel, outcome in notify_results.items():
                print(f"  {channel}: {outcome}")
        else:
            print("\nNo notifications sent (nothing new above min_score).")


@app.command()
def list(
    board: str | None = typer.Option(None, "--board", help="Only this board"),
    status: str | None = typer.Option(None, "--status", help="new / saved / applied / hidden"),
    limit: int = typer.Option(50, "--limit"),
):
    """List Rwanda-eligible jobs."""
    _fix_console_encoding()
    rows = _store().list_jobs(board=board, eligible_only=True, status=status, limit=limit)
    if not rows:
        print("No jobs found. Run `python -m job_hunter discover` first.")
        return
    for r in rows:
        loc = f" | {r['location'][:25]}" if r["location"] else ""
        fit = f" | fit {r['score']:>3}" if r["score"] else ""
        print(f"[{r['id']:>4}] {r['title'][:55]} @ {r['company'][:22]:<22} "
              f"| {r['board']:<14}{loc}{fit}")
        if r["url"]:
            print(f"       {r['url']}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search keyword (title/company/description)"),
    board: str | None = typer.Option(None, "--board", help="Only this board"),
    limit: int = typer.Option(30, "--limit"),
):
    """Search jobs by keyword."""
    _fix_console_encoding()
    rows = _store().search(query=query, board=board, limit=limit)
    if not rows:
        print(f"No jobs match '{query}'.")
        return
    print(f"Found {len(rows)} job(s) matching '{query}':")
    for r in rows:
        loc = f" | {r['location'][:25]}" if r["location"] else ""
        print(f"  [{r['id']:>4}] {r['title'][:50]:50s} @ {r['company'][:20]:20s} | {r['board']}{loc}")
    print(f"\nUse `job-hunter details <id>` for full info.")


@app.command()
def details(job_id: int = typer.Argument(..., help="Job ID")):
    """Show full details of a job."""
    _fix_console_encoding()
    r = _store().get_job(job_id)
    if not r:
        print(f"Job #{job_id} not found.")
        return
    print(f"{'='*70}")
    print(f"  #{r['id']}  {r['title']}")
    print(f"{'='*70}")
    print(f"  Company:    {r['company']}")
    print(f"  Board:      {r['board']}")
    print(f"  Status:     {r['status']}")
    print(f"  Location:   {r['location'] or '(not listed)'}")
    if r['remote']:
        print(f"  Remote:     {r['remote']}")
    print(f"  URL:        {r['url']}")
    if r['eligibility_note']:
        print(f"  Eligible:   {r['eligibility_note']}")
    if r['score']:
        print(f"  Fit score:  {r['score']}/100 ({r['score_reasons']})")
    if r['posted_at']:
        print(f"  Posted:     {r['posted_at']}")
    print(f"  Found:      {r['found_at']}")
    desc = (r['description'] or '').strip()
    if desc:
        print(f"\n{'-'*70}")
        print(f"  Description (first 500 chars):")
        print(f"{'-'*70}")
        print(f"  {desc[:500]}")
        if len(desc) > 500:
            print(f"  ... ({len(desc) - 500} more chars)")
    print(f"\nActions: `job-hunter mark {job_id} saved` or `job-hunter mark {job_id} applied`")


@app.command()
def status():
    """Show how many jobs are stored, per board."""
    _fix_console_encoding()
    s = _store().stats()
    print(f"Total: {s['total']}  (eligible-only store)")
    for board, n in s["by_board"].items():
        print(f"  {board:<16} {n}")


@app.command()
def mark(job_id: int, status: str):
    """Set a job's status: new / saved / applied / hidden."""
    statuses = {"new", "saved", "applied", "hidden"}
    if status not in statuses:
        raise typer.BadParameter(f"status must be one of {sorted(statuses)}")
    ok = _store().mark(job_id, status)
    if ok:
        print(f"Job #{job_id} marked as {status}")
    else:
        print(f"Job #{job_id} not found")


@app.command()
def purge(status: str = typer.Argument("hidden", help="Status to delete (default: hidden)")):
    """Delete jobs with the given status."""
    n = _store().purge(status)
    print(f"Deleted {n} {status} job(s)")


@app.command()
def watch(
    interval: int = typer.Option(3600, "--interval", help="Seconds between discovery runs"),
    runs: int = typer.Option(0, "--runs", help="Stop after N runs (0 = run forever)"),
):
    """Run discovery repeatedly, sleeping `--interval` seconds between runs.

    For a long-lived process (a server, a VPS, a Docker container). For a
    one-shot cron job, call `job-hunter discover` directly from cron instead.
    """
    _fix_console_encoding()
    from job_hunter.orchestrator import notify_new_jobs, run_discover

    cfg = load_config()
    count = 0
    print(f"Watching every {interval}s. Ctrl+C to stop.")
    try:
        while True:
            count += 1
            print(f"\n=== run {count} ===")
            results = run_discover(cfg)
            added = sum(r.get("added", 0) for r in results)
            errored = [r["board"] for r in results if r["error"]]
            print(f"  added={added} errors={errored or 'none'}")
            if cfg.notifications.enabled:
                notify_results = notify_new_jobs(cfg)
                if notify_results:
                    print(f"  notified: {notify_results}")
            if runs and count >= runs:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")


@app.command(name="notify-test")
def notify_test():
    """Send a fake job to every configured notification channel, to verify setup."""
    _fix_console_encoding()
    from datetime import datetime, timezone

    from job_hunter import notifications

    cfg = load_config()
    if not cfg.notifications.enabled:
        print("Notifications are disabled. Set notifications.enabled: true in config.yaml.")
        raise typer.Exit(1)

    fake = {
        "title": "Test Notification", "company": "job-hunter", "board": "test",
        "location": "Remote", "score": 100, "url": "https://example.com/test",
    }

    class _Row(dict):
        def __getitem__(self, key):
            return dict.get(self, key, "")

    results = notifications.send_digest([_Row(fake)], cfg.notifications)
    if not results:
        print("No channels configured (set telegram_*, webhook_url, or smtp_* in config.yaml).")
        raise typer.Exit(1)
    for channel, outcome in results.items():
        print(f"  {channel}: {outcome}")


@app.command()
def analyze(
    check_links: bool = typer.Option(True, "--check-links/--skip-links", help="Validate URLs (slower but thorough)"),
    batch_size: int = typer.Option(10, help="Concurrent link checks"),
):
    """Analyze jobs: validate links, check quality, remove dead/duplicates."""
    _fix_console_encoding()
    import asyncio
    from job_hunter.analyzer import analyze as run_analysis, print_summary

    cfg = load_config()
    print("Running job analysis...")
    summary = asyncio.run(run_analysis(cfg.database, check_links=check_links, batch_size=batch_size))
    print_summary(summary)


@app.command()
def cleanup(
    stale_days: int = typer.Option(30, help="Remove jobs older than N days"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Clean database: re-check eligibility, remove stale/duplicates."""
    _fix_console_encoding()
    from job_hunter.cleanup import full_cleanup

    cfg = load_config()

    if not yes:
        print("This will:")
        print("  1. Re-check eligibility on all jobs (remove ones that no longer qualify)")
        print(f"  2. Remove jobs older than {stale_days} days with status 'new'")
        print("  3. Remove duplicates (keep newest)")
        if not typer.confirm("Continue?"):
            print("Cancelled.")
            return

    result = full_cleanup(cfg.database, stale_days)

    print(f"\nCleanup complete:")
    print(f"  Eligibility removed: {result['eligibility_removed']}")
    print(f"  Stale removed:       {result['stale_removed']}")
    print(f"  Duplicates removed:  {result['dupes_removed']}")
    print(f"  Final total:         {result['final_total']}")
    print(f"  Final eligible:      {result['final_eligible']}")


@app.command(name="sync")
def sync_db(
    vps_host: str = typer.Option("", help="VPS hostname/IP"),
    vps_user: str = typer.Option("root", help="SSH user"),
    vps_pass: str = typer.Option("", help="SSH password"),
    vps_path: str = typer.Option("/root/job-hunter/data/jobs.db", help="Remote DB path"),
    local_db: str = typer.Option("", help="Local DB path (auto-detected if empty)"),
):
    """Push local DB to VPS so the dashboard shows fresh data."""
    try:
        import paramiko
    except ImportError:
        print("Error: pip install paramiko")
        raise typer.Exit(1)

    cfg = load_config()
    src = local_db or cfg.database
    if not Path(src).exists():
        print(f"Local DB not found: {src}")
        raise typer.Exit(1)

    if not vps_host:
        print("Provide --vps-host (e.g. 72.60.188.94)")
        raise typer.Exit(1)
    if not vps_pass:
        print("Provide --vps-pass")
        raise typer.Exit(1)

    size_mb = Path(src).stat().st_size / (1024 * 1024)
    print(f"Syncing {src} ({size_mb:.1f} MB) → {vps_user}@{vps_host}:{vps_path}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(vps_host, username=vps_user, password=vps_pass, look_for_keys=False)
    print("Connected to VPS")

    # Stop container to release DB lock
    print("Stopping container...")
    ssh.exec_command("docker stop job-hunter")
    time.sleep(3)

    # Upload
    print("Uploading DB...")
    sftp = ssh.open_sftp()
    sftp.put(src, vps_path)
    sftp.close()

    # Restart
    print("Starting container...")
    ssh.exec_command("docker start job-hunter")
    time.sleep(5)

    # Verify
    check_script = f'import sqlite3; c=sqlite3.connect("{vps_path}"); print(c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])'
    _, out, _ = ssh.exec_command(f'python3 -c "{check_script}"')
    count = out.read().decode().strip()
    print(f"✅ VPS now has {count} jobs")

    ssh.close()
    print("Done! Open http://{}:8001".format(vps_host))


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
):
    """Launch the web dashboard."""
    import uvicorn
    print(f"Starting dashboard at http://{host}:{port}")
    uvicorn.run(
        "job_hunter.dashboard.server:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    app()
