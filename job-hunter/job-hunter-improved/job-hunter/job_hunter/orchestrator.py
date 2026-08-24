"""Discovery orchestrator: run boards, filter for Rwanda eligibility + keyword
relevance, store to SQLite, and report results."""

from __future__ import annotations

import asyncio
import sys

from job_hunter import eligibility, scoring
from job_hunter.boards import BOARDS
from job_hunter.boards.base import Board
from job_hunter.boards.remoteok import RemoteOKBoard
from job_hunter.boards.ats import ATSBoard
from job_hunter.boards.scam_filter import is_unreliable
from job_hunter.config import Config
from job_hunter.models import Job, Store


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _make_board(name: str, cfg: Config) -> Board:
    """Create a board instance with the right config for this run."""
    if name == "remoteok":
        return RemoteOKBoard(tags=cfg.keywords)
    if name == "ats":
        return ATSBoard(companies=[c.model_dump() for c in cfg.ats_companies])
    cls = BOARDS.get(name)
    if cls:
        return cls()
    raise ValueError(f"Unknown board: {name}")


async def _run_board(name: str, store: Store, cfg: Config) -> dict:
    board = _make_board(name, cfg)
    try:
        jobs = await board.fetch(limit=cfg.max_jobs_per_board)
    except Exception as exc:
        return {"board": name, "fetched": 0, "error": f"{type(exc).__name__}: {exc}"}

    added = eligible = duplicates = unreliable = 0
    for job in jobs:
        # Scam/unreliable filter
        is_bad, bad_reason = is_unreliable(
            title=job.title, company=job.company, description=job.description
        )
        if is_bad:
            unreliable += 1
            continue

        ok, note = eligibility.check_eligibility(job)
        if not ok:
            continue  # store only Rwanda-eligible roles
        if not eligibility.matches_keywords(job, cfg.keywords):
            continue
        eligible += 1
        score, reasons = scoring.score_job(
            job, cfg.profile.skills, seniority=cfg.profile.seniority
        )
        result = store.add_job(job, ok, note, score=score, score_reasons=reasons)
        if result == "new":
            added += 1
        elif result == "duplicate":
            duplicates += 1

    return {
        "board": name,
        "fetched": len(jobs),
        "eligible": eligible,
        "added": added,
        "duplicates": duplicates,
        "unreliable": unreliable,
        "error": None,
    }


async def discover(cfg: Config) -> list[dict]:
    store = Store(cfg.database)
    results = await asyncio.gather(
        *(_run_board(name, store, cfg) for name, enabled in cfg.boards.items() if enabled)
    )
    return results


def run_discover(cfg: Config) -> list[dict]:
    return asyncio.run(discover(cfg))


def notify_new_jobs(cfg: Config) -> dict:
    """Send a digest of not-yet-notified eligible jobs, if notifications are
    configured and enabled. Marks whatever was sent as notified so the next
    run doesn't repeat it. Returns {} if notifications are off or there's
    nothing new to send.
    """
    if not cfg.notifications.enabled:
        return {}
    from job_hunter import notifications  # local import: httpx/smtplib not
                                           # needed unless notifications run

    store = Store(cfg.database)
    jobs = [
        j for j in store.unnotified(limit=200)
        if j["score"] >= cfg.notifications.min_score
    ]
    if not jobs:
        return {}
    results = notifications.send_digest(jobs, cfg.notifications)
    # Mark notified even on partial failure — the digest was attempted for
    # every channel; retrying the same jobs every run would spam once a
    # single channel recovers.
    if results:
        store.mark_notified([j["id"] for j in jobs])
    return results


def run_discover_and_notify(cfg: Config) -> tuple[list[dict], dict]:
    """Run discovery, then send a notification digest for anything new."""
    results = run_discover(cfg)
    notify_results = notify_new_jobs(cfg)
    return results, notify_results
