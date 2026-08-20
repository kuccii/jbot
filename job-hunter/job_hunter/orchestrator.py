"""Discovery orchestrator: run boards, filter for Rwanda eligibility + keyword
relevance, store to SQLite, and report results."""

from __future__ import annotations

import asyncio
import sys

from job_hunter import eligibility
from job_hunter.boards import BOARDS
from job_hunter.boards.base import Board
from job_hunter.boards.remoteok import RemoteOKBoard
from job_hunter.boards.ats import ATSBoard
from job_hunter.boards.scam_filter import is_unreliable
from job_hunter.config import Config
from job_hunter.models import Job, Store, AUDIENCE_TECH, AUDIENCE_ENTRY, AUDIENCE_GIG


# Default audience tags per board. Indeed sets its own per-skill.
_BOARD_AUDIENCE: dict[str, str] = {
    "remoteok": AUDIENCE_TECH,
    "remote4africa": AUDIENCE_TECH,
    "himalayas": AUDIENCE_TECH,
    "remotive": AUDIENCE_TECH,
    "jobicy": AUDIENCE_TECH,
    "workingnomads": AUDIENCE_TECH,
    "persona": AUDIENCE_TECH,
    "ats": AUDIENCE_TECH,
    "arc": AUDIENCE_TECH,
    "foundthejob": AUDIENCE_ENTRY,
    "opentrain": AUDIENCE_GIG,
    "dynamitejobs": AUDIENCE_TECH,
    "trulyremote": AUDIENCE_TECH,
    "gig_platforms": AUDIENCE_GIG,
    "startupjobs": AUDIENCE_TECH,
    "meetfrank": AUDIENCE_TECH,
    "workday": AUDIENCE_ENTRY,
    "entry_platforms": AUDIENCE_ENTRY,
    "indeed_entry": AUDIENCE_ENTRY,
    "wwr_entry": AUDIENCE_ENTRY,
}


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
        # Auto-tag audience if the board didn't set one
        if not job.audience:
            job.audience = _BOARD_AUDIENCE.get(name, AUDIENCE_TECH)
        eligible += 1
        result = store.add_job(job, ok, note)
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
