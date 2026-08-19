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

    added = eligible = duplicates = 0
    for job in jobs:
        ok, note = eligibility.check_eligibility(job)
        if not ok:
            continue  # store only Rwanda-eligible roles
        if not eligibility.matches_keywords(job, cfg.keywords):
            continue
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
