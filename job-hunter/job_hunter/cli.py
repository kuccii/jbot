"""CLI for job-hunter.

Run from the job-hunter/ folder:

    python -m job_hunter discover   # fetch jobs from enabled boards
    python -m job_hunter list       # show Rwanda-eligible jobs
    python -m job_hunter status     # counts per board
    python -m job_hunter mark 12 applied
    python -m job_hunter purge hidden
"""

from __future__ import annotations

import sys

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
def discover():
    """Fetch jobs from all enabled boards and store Rwanda-eligible ones."""
    _fix_console_encoding()
    from job_hunter.orchestrator import run_discover

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
        print(f"[{r['id']:>4}] {r['title'][:60]} @ {r['company'][:28]:<28} "
              f"| {r['board']:<14} | {r['status']}")
        if r["eligibility_note"]:
            print(f"       → {r['eligibility_note']}")
        if r["url"]:
            print(f"       {r['url']}")


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


if __name__ == "__main__":
    app()
