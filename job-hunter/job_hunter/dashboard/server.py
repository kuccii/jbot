"""Job Hunter Dashboard — FastAPI web app with smart discovery control.

Run with:
    python -m job_hunter.dashboard.server

Or from CLI:
    job-hunter dashboard
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import queue

from job_hunter.config import load_config, Config
from job_hunter.models import SCHEMA

app = FastAPI(title="Job Hunter Dashboard", version="2.0.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# Discovery state — tracks per-board progress in real time
# ---------------------------------------------------------------------------
_discovery_state: dict[str, Any] = {
    "running": False,
    "mode": None,           # "quick" | "entry" | "full" | "custom" | "single"
    "started_at": None,
    "elapsed": 0,
    "boards": {},           # {board_name: {status, fetched, eligible, added, error}}
    "last_result": None,
    "last_run": None,
    "total_boards": 0,
    "completed_boards": 0,
}

# Board registry — metadata for every board
BOARD_REGISTRY: dict[str, dict] = {
    # ── Fast / Reliable (API-based) ────────────────────────────────────────
    "remoteok":       {"category": "remote",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Remote developer jobs (JSON API)"},
    "arc":            {"category": "remote",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Remote developer marketplace"},
    "ats":            {"category": "ats",       "audience": "tech",    "speed": "medium", "cost": "free",  "reliability": "high",   "desc": "101 company ATS APIs (Greenhouse/Ashby)"},
    "himalayas":      {"category": "remote",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Worldwide remote jobs"},
    "jobicy":         {"category": "remote",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Remote jobs by geo-location"},
    "remotive":       {"category": "remote",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Curated remote jobs"},
    "remote4africa":  {"category": "africa",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Africa-focused remote jobs"},
    "persona":        {"category": "remote",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Persona Talent remote jobs"},
    "workingnomads":  {"category": "remote",    "audience": "tech",    "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Digital nomad jobs"},
    # ── Entry-Level ────────────────────────────────────────────────────────
    "indeed_entry":   {"category": "entry",     "audience": "entry",   "speed": "slow",   "cost": "free",  "reliability": "medium", "desc": "Indeed entry-level jobs (19 countries)"},
    "entry_platforms": {"category": "entry",    "audience": "entry",   "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Curated sign-up job platforms"},
    "wwr_entry":      {"category": "entry",     "audience": "entry",   "speed": "medium", "cost": "free",  "reliability": "medium", "desc": "WeWorkRemotely customer support"},
    "workday":        {"category": "entry",     "audience": "entry",   "speed": "slow",   "cost": "free",  "reliability": "medium", "desc": "ModSquad BPO remote positions"},
    "foundthejob":    {"category": "entry",     "audience": "entry",   "speed": "medium", "cost": "free",  "reliability": "medium", "desc": "WordPress job board"},
    # ── Indeed Main ────────────────────────────────────────────────────────
    "indeed":         {"category": "indeed",    "audience": "mixed",   "speed": "slow",   "cost": "free",  "reliability": "low",    "desc": "Indeed main search (19 countries)"},
    # ── Startups ───────────────────────────────────────────────────────────
    "startupjobs":    {"category": "startup",   "audience": "tech",    "speed": "slow",   "cost": "free",  "reliability": "low",    "desc": "Startup Jobs remote positions"},
    "meetfrank":      {"category": "startup",   "audience": "tech",    "speed": "slow",   "cost": "free",  "reliability": "low",    "desc": "European startup jobs"},
    # ── Gig / AI Training ─────────────────────────────────────────────────
    "opentrain":      {"category": "gig",       "audience": "gig",     "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "OpenTrain AI data labeling"},
    "gig_platforms":  {"category": "gig",       "audience": "gig",     "speed": "fast",   "cost": "free",  "reliability": "high",   "desc": "Curated gig/RLHF platforms"},
    # ── SPA / JS-Rendered (may fail) ──────────────────────────────────────
    "dynamitejobs":   {"category": "spa",       "audience": "tech",    "speed": "slow",   "cost": "free",  "reliability": "low",    "desc": "Remote jobs (JS-rendered)"},
    "trulyremote":    {"category": "spa",       "audience": "tech",    "speed": "slow",   "cost": "free",  "reliability": "low",    "desc": "Pre-screened remote (JS-rendered)"},
    # ── Extra ──────────────────────────────────────────────────────────────
    "weworkremotely": {"category": "remote",    "audience": "tech",    "speed": "medium", "cost": "free",  "reliability": "low",    "desc": "WeWorkRemotely (403 from datacenter)"},
    # ── Web-Search powered (SearXNG on VPS) ────────────────────────────────
    "indeed_search":  {"category": "search",    "audience": "entry",   "speed": "slow",   "cost": "free",  "reliability": "high",   "desc": "Indeed real viewjob links via SearXNG web search"},
    "visa_sponsorship": {"category": "search",  "audience": "visa",    "speed": "slow",   "cost": "free",  "reliability": "medium", "desc": "Employers offering visa sponsorship / relocation"},
}

# Preset modes
PRESETS = {
    "quick": {
        "name": "⚡ Quick",
        "desc": "Fast boards only (~30 seconds)",
        "boards": ["remoteok", "arc", "himalayas", "jobicy", "remotive", "remote4africa", "ats"],
    },
    "entry": {
        "name": "🚀 Entry-Level",
        "desc": "Entry-level + gig platforms",
        "boards": ["indeed_entry", "entry_platforms", "wwr_entry", "workday", "foundthejob", "gig_platforms", "opentrain"],
    },
    "full": {
        "name": "🌐 Full Scan",
        "desc": "All enabled boards (may take 5+ minutes)",
        "boards": list(BOARD_REGISTRY.keys()),
    },
    "africa": {
        "name": "🌍 Africa Focus",
        "desc": "Africa-specific + worldwide remote",
        "boards": ["remote4africa", "remoteok", "arc", "himalayas", "jobicy", "remotive", "ats", "persona", "workingnomads"],
    },
    "ats_only": {
        "name": "🏢 ATS APIs",
        "desc": "101 company Greenhouse/Ashby/SmartRecruiters",
        "boards": ["ats"],
    },
}


def _get_db() -> sqlite3.Connection:
    """Get database connection, ensuring tables exist."""
    cfg = load_config()
    conn = sqlite3.connect(cfg.database)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Discovery engine — runs boards with real-time progress tracking
# ---------------------------------------------------------------------------

def _run_board_with_progress(name: str, cfg: Config, result_queue: queue.Queue) -> None:
    """Run a single board and report progress to the queue."""
    import job_hunter.boards
    from job_hunter.boards.base import Board
    from job_hunter.boards.remoteok import RemoteOKBoard
    from job_hunter.boards.ats import ATSBoard
    from job_hunter.boards.scam_filter import is_unreliable
    from job_hunter import eligibility, scoring
    from job_hunter.models import Store, AUDIENCE_TECH, AUDIENCE_ENTRY, AUDIENCE_GIG

    _BOARD_AUDIENCE: dict[str, str] = {
        "remoteok": AUDIENCE_TECH, "remote4africa": AUDIENCE_TECH,
        "himalayas": AUDIENCE_TECH, "remotive": AUDIENCE_TECH,
        "jobicy": AUDIENCE_TECH, "workingnomads": AUDIENCE_TECH,
        "persona": AUDIENCE_TECH, "ats": AUDIENCE_TECH, "arc": AUDIENCE_TECH,
        "foundthejob": AUDIENCE_ENTRY, "opentrain": AUDIENCE_GIG,
        "dynamitejobs": AUDIENCE_TECH, "trulyremote": AUDIENCE_TECH,
        "gig_platforms": AUDIENCE_GIG, "startupjobs": AUDIENCE_TECH,
        "meetfrank": AUDIENCE_TECH, "workday": AUDIENCE_ENTRY,
        "entry_platforms": AUDIENCE_ENTRY, "indeed_entry": AUDIENCE_ENTRY,
        "wwr_entry": AUDIENCE_ENTRY,
        "indeed_search": AUDIENCE_ENTRY,
        "visa_sponsorship": AUDIENCE_ENTRY,
    }

    # Report: starting
    result_queue.put({"board": name, "status": "fetching", "fetched": 0, "eligible": 0, "added": 0})

    try:
        # Create board from registry
        from job_hunter.boards import BOARDS
        if name == "remoteok":
            board = RemoteOKBoard(tags=cfg.keywords)
        elif name == "ats":
            board = ATSBoard(companies=[c.model_dump() for c in cfg.ats_companies])
        elif name in BOARDS:
            board = BOARDS[name]()
        else:
            result_queue.put({"board": name, "status": "error", "error": f"No board class: {name}"})
            return

        # Report: fetching
        result_queue.put({"board": name, "status": "fetching", "fetched": 0, "eligible": 0, "added": 0})

        # All board fetch() methods are async — run in a fresh event loop for this thread
        jobs = asyncio.run(board.fetch(limit=cfg.max_jobs_per_board))

        result_queue.put({"board": name, "status": "filtering", "fetched": len(jobs), "eligible": 0, "added": 0})

        # Filter and store
        store = Store(cfg.database)
        added = eligible = duplicates = unreliable = 0

        for job in jobs:
            is_bad, _ = is_unreliable(title=job.title, company=job.company, description=job.description)
            if is_bad:
                unreliable += 1
                continue
            if name == "visa_sponsorship":
                ok, note = eligibility.check_visa_sponsorship(job)
            else:
                ok, note = eligibility.check_eligibility(job)
            if not ok:
                continue
            if not eligibility.matches_keywords(job, cfg.keywords):
                continue
            if not job.audience:
                job.audience = _BOARD_AUDIENCE.get(name, AUDIENCE_TECH)
            eligible += 1
            score, reasons = scoring.score_job(job, cfg.profile.skills, seniority=cfg.profile.seniority)
            result = store.add_job(job, ok, note, score=score, score_reasons=reasons)
            if result == "new":
                added += 1
            elif result == "duplicate":
                duplicates += 1

        result_queue.put({
            "board": name, "status": "done",
            "fetched": len(jobs), "eligible": eligible, "added": added,
            "duplicates": duplicates, "unreliable": unreliable, "error": None,
        })

    except Exception as e:
        result_queue.put({"board": name, "status": "error", "error": f"{type(e).__name__}: {e}", "fetched": 0, "eligible": 0, "added": 0})


def _run_discovery_thread(board_names: list[str], mode: str) -> None:
    """Run discovery in background, updating _discovery_state per board."""
    import queue

    _discovery_state["running"] = True
    _discovery_state["mode"] = mode
    _discovery_state["started_at"] = time.time()
    _discovery_state["boards"] = {n: {"status": "queued", "fetched": 0, "eligible": 0, "added": 0} for n in board_names}
    _discovery_state["total_boards"] = len(board_names)
    _discovery_state["completed_boards"] = 0

    try:
        cfg = load_config()
        q: queue.Queue = queue.Queue()

        # Run boards concurrently (max 5 at a time to avoid hammering)
        threads: list[threading.Thread] = []
        semaphore = threading.Semaphore(5)

        def _run_with_semaphore(name: str):
            with semaphore:
                _run_board_with_progress(name, cfg, q)

        for name in board_names:
            t = threading.Thread(target=_run_with_semaphore, args=(name,), daemon=True)
            threads.append(t)
            t.start()

        # Consume progress updates while threads run
        while any(t.is_alive() for t in threads):
            try:
                update = q.get(timeout=0.5)
                board_name = update["board"]
                _discovery_state["boards"][board_name] = update
                if update["status"] in ("done", "error"):
                    _discovery_state["completed_boards"] += 1
                _discovery_state["elapsed"] = round(time.time() - _discovery_state["started_at"], 1)
            except queue.Empty:
                _discovery_state["elapsed"] = round(time.time() - _discovery_state["started_at"], 1)

        # Drain remaining
        while not q.empty():
            update = q.get_nowait()
            board_name = update["board"]
            _discovery_state["boards"][board_name] = update
            if update["status"] in ("done", "error"):
                _discovery_state["completed_boards"] += 1

        # Summary
        total_added = sum(b.get("added", 0) for b in _discovery_state["boards"].values())
        total_fetched = sum(b.get("fetched", 0) for b in _discovery_state["boards"].values())
        errors = [n for n, b in _discovery_state["boards"].items() if b.get("status") == "error"]

        _discovery_state["last_result"] = {
            "mode": mode,
            "boards_run": len(board_names),
            "total_fetched": total_fetched,
            "total_new": total_added,
            "errors": errors,
        }
        _discovery_state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        _discovery_state["last_result"] = {"error": str(e)}
    finally:
        _discovery_state["running"] = False
        _discovery_state["elapsed"] = round(time.time() - _discovery_state["started_at"], 1) if _discovery_state["started_at"] else 0


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Dashboard home — stats + discovery control."""
    conn = _get_db()
    try:
        stats = _get_stats(conn)
        recent = conn.execute(
            """SELECT * FROM jobs WHERE eligible=1
               ORDER BY CASE WHEN audience='entry' THEN 0 WHEN audience='visa' THEN 1 WHEN audience='gig' THEN 2 WHEN audience='creative' THEN 3 ELSE 4 END,
               score DESC, found_at DESC LIMIT 12"""
        ).fetchall()
        return templates.TemplateResponse(request, "home.html", {
            "stats": stats,
            "recent": recent,
            "discovery": _discovery_state,
            "board_registry": BOARD_REGISTRY,
            "presets": PRESETS,
        })
    finally:
        conn.close()


@app.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request,
    board: str = Query("", help="Filter by board"),
    status: str = Query("", help="Filter by status"),
    search: str = Query("", help="Search keywords"),
    audience: str = Query("", help="Filter by audience"),
    sort: str = Query("entry_first", help="entry_first, found_at, or score"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=5, le=100),
):
    """Job listing page with filters. Default: entry-level first."""
    conn = _get_db()
    try:
        jobs, total, pages = _query_jobs(conn, board, status, search, audience, page, per_page, sort)
        boards = [r["board"] for r in conn.execute(
            "SELECT DISTINCT board FROM jobs WHERE eligible=1 ORDER BY board"
        ).fetchall()]
        return templates.TemplateResponse(request, "jobs.html", {
            "jobs": jobs,
            "total": total,
            "page": page,
            "pages": pages,
            "boards": boards,
            "filters": {"board": board, "status": status, "search": search, "audience": audience, "sort": sort},
        })
    finally:
        conn.close()


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    """Job detail page."""
    conn = _get_db()
    try:
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            return templates.TemplateResponse(request, "404.html", {}, status_code=404)
        return templates.TemplateResponse(request, "detail.html", {"job": job})
    finally:
        conn.close()


@app.post("/jobs/{job_id}/status")
async def update_status(job_id: int, status: str = Query(...)):
    """Update job status (new/saved/applied/hidden)."""
    conn = _get_db()
    try:
        conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        conn.commit()
        return JSONResponse({"ok": True})
    finally:
        conn.close()


@app.get("/platforms", response_class=HTMLResponse)
async def platforms_page(request: Request):
    """Platforms page with audience tabs."""
    conn = _get_db()
    try:
        platforms = conn.execute("SELECT * FROM jobs WHERE board='gig_platforms' AND eligible=1 ORDER BY title").fetchall()
        ai_gigs = conn.execute("SELECT * FROM jobs WHERE board='opentrain' AND eligible=1 ORDER BY found_at DESC LIMIT 20").fetchall()
        indeed_jobs = conn.execute("SELECT * FROM jobs WHERE board='indeed' AND eligible=1 ORDER BY title LIMIT 30").fetchall()
        entry_platforms = conn.execute("SELECT * FROM jobs WHERE board='entry_platforms' AND eligible=1 ORDER BY title").fetchall()
        workday_jobs = conn.execute("SELECT * FROM jobs WHERE board='workday' AND eligible=1 ORDER BY found_at DESC LIMIT 20").fetchall()
        entry_jobs = conn.execute("SELECT * FROM jobs WHERE eligible=1 AND audience='entry' ORDER BY found_at DESC LIMIT 30").fetchall()
        creative_jobs = conn.execute("SELECT * FROM jobs WHERE eligible=1 AND audience='creative' ORDER BY found_at DESC LIMIT 30").fetchall()
        tech_jobs = conn.execute("SELECT * FROM jobs WHERE eligible=1 AND audience='tech' ORDER BY found_at DESC LIMIT 30").fetchall()
        return templates.TemplateResponse(request, "platforms.html", {
            "platforms": platforms, "entry_platforms": entry_platforms,
            "workday_jobs": workday_jobs, "ai_gigs": ai_gigs, "indeed_jobs": indeed_jobs,
            "entry_jobs": entry_jobs, "creative_jobs": creative_jobs, "tech_jobs": tech_jobs,
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API — Board registry + discovery control
# ---------------------------------------------------------------------------

@app.get("/api/boards")
async def api_boards():
    """List all boards with metadata and last-known status from DB."""
    conn = _get_db()
    try:
        # Get per-board stats from DB
        board_stats = {}
        for row in conn.execute(
            "SELECT board, COUNT(*) as n, MAX(found_at) as last_found FROM jobs GROUP BY board"
        ).fetchall():
            board_stats[row["board"]] = {"count": row["n"], "last_found": row["last_found"]}

        result = []
        for name, meta in BOARD_REGISTRY.items():
            db_info = board_stats.get(name, {"count": 0, "last_found": None})
            result.append({
                "name": name,
                **meta,
                "db_count": db_info["count"],
                "last_found": db_info["last_found"],
            })
        return result
    finally:
        conn.close()


@app.get("/api/presets")
async def api_presets():
    """List discovery presets."""
    return PRESETS


@app.post("/api/discover")
async def api_discover():
    """Start a full discovery run (all enabled boards)."""
    if _discovery_state["running"]:
        return JSONResponse({"status": "already_running", "elapsed": _discovery_state["elapsed"]})

    cfg = load_config()
    board_names = [n for n, enabled in cfg.boards.items() if enabled]
    threading.Thread(target=_run_discovery_thread, args=(board_names, "full"), daemon=True).start()
    return JSONResponse({"status": "started", "mode": "full", "boards": board_names})


@app.post("/api/discover/preset/{preset_name}")
async def api_discover_preset(preset_name: str):
    """Start discovery with a preset mode."""
    if _discovery_state["running"]:
        return JSONResponse({"status": "already_running", "elapsed": _discovery_state["elapsed"]})

    if preset_name not in PRESETS:
        return JSONResponse({"error": f"Unknown preset: {preset_name}. Available: {list(PRESETS.keys())}"}, status_code=400)

    preset = PRESETS[preset_name]
    # Filter to only enabled boards
    cfg = load_config()
    board_names = [n for n in preset["boards"] if cfg.boards.get(n, True)]

    threading.Thread(target=_run_discovery_thread, args=(board_names, preset_name), daemon=True).start()
    return JSONResponse({"status": "started", "mode": preset_name, "boards": board_names})


@app.post("/api/discover/boards")
async def api_discover_custom(request: Request):
    """Start discovery with a custom board selection."""
    if _discovery_state["running"]:
        return JSONResponse({"status": "already_running", "elapsed": _discovery_state["elapsed"]})

    body = await request.json()
    board_names = body.get("boards", [])
    if not board_names:
        return JSONResponse({"error": "No boards selected"}, status_code=400)

    # Validate
    valid = [n for n in board_names if n in BOARD_REGISTRY]
    if not valid:
        return JSONResponse({"error": "No valid boards in selection"}, status_code=400)

    threading.Thread(target=_run_discovery_thread, args=(valid, "custom"), daemon=True).start()
    return JSONResponse({"status": "started", "mode": "custom", "boards": valid})


@app.post("/api/discover/single/{board_name}")
async def api_discover_single(board_name: str):
    """Run discovery for a single board."""
    if _discovery_state["running"]:
        return JSONResponse({"status": "already_running", "elapsed": _discovery_state["elapsed"]})

    if board_name not in BOARD_REGISTRY:
        return JSONResponse({"error": f"Unknown board: {board_name}"}, status_code=400)

    threading.Thread(target=_run_discovery_thread, args=([board_name], "single"), daemon=True).start()
    return JSONResponse({"status": "started", "mode": "single", "boards": [board_name]})


@app.get("/api/discover/status")
async def api_discover_status():
    """Get real-time discovery progress."""
    return _discovery_state


@app.get("/api/stats")
async def api_stats():
    """JSON stats for charts."""
    conn = _get_db()
    try:
        return _get_stats(conn)
    finally:
        conn.close()


@app.get("/api/jobs")
async def api_jobs(
    board: str = "", status: str = "", search: str = "",
    audience: str = "", sort: str = "found_at",
    page: int = 1, per_page: int = 25,
):
    """JSON job listing."""
    conn = _get_db()
    try:
        jobs, total, pages = _query_jobs(conn, board, status, search, audience, page, per_page, sort)
        return {"jobs": [dict(j) for j in jobs], "total": total, "page": page, "pages": pages}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_stats(conn: sqlite3.Connection) -> dict:
    """Get dashboard statistics."""
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    eligible = conn.execute("SELECT COUNT(*) FROM jobs WHERE eligible=1").fetchone()[0]

    by_board = {
        r["board"]: r["n"]
        for r in conn.execute(
            "SELECT board, COUNT(*) as n FROM jobs WHERE eligible=1 GROUP BY board ORDER BY n DESC"
        ).fetchall()
    }

    by_status = {
        r["status"]: r["n"]
        for r in conn.execute(
            "SELECT status, COUNT(*) as n FROM jobs GROUP BY status ORDER BY n DESC"
        ).fetchall()
    }

    by_audience = {
        r["audience"]: r["n"]
        for r in conn.execute(
            """SELECT CASE WHEN audience='' THEN 'untagged' ELSE audience END as audience,
                      COUNT(*) as n FROM jobs WHERE eligible=1
               GROUP BY audience ORDER BY n DESC"""
        ).fetchall()
    }

    daily = [
        {"date": r["date"], "count": r["n"]}
        for r in conn.execute(
            """SELECT DATE(found_at) as date, COUNT(*) as n
               FROM jobs WHERE eligible=1
               GROUP BY DATE(found_at) ORDER BY date DESC LIMIT 7"""
        ).fetchall()
    ]

    return {
        "total": total, "eligible": eligible,
        "by_board": by_board, "by_status": by_status,
        "by_audience": by_audience, "daily": daily,
    }


def _query_jobs(
    conn: sqlite3.Connection,
    board: str, status: str, search: str, audience: str,
    page: int, per_page: int, sort: str = "found_at",
) -> tuple[list, int, int]:
    """Query jobs with filters, return (jobs, total, total_pages)."""
    where = ["eligible=1"]
    params: list = []

    if board:
        where.append("board=?")
        params.append(board)
    if status:
        where.append("status=?")
        params.append(status)
    if audience:
        where.append("audience LIKE ?")
        params.append(f"%{audience}%")
    if search:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        q = f"%{search}%"
        params.extend([q, q, q])

    where_clause = " AND ".join(where)
    if sort == "score":
        order_clause = "score DESC, found_at DESC"
    elif sort == "found_at":
        order_clause = "found_at DESC"
    else:  # entry_first (default)
        order_clause = "CASE WHEN audience='entry' THEN 0 WHEN audience='visa' THEN 1 WHEN audience='gig' THEN 2 WHEN audience='creative' THEN 3 ELSE 4 END, score DESC, found_at DESC"

    total = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_clause}", params
    ).fetchone()[0]
    pages = max(1, (total + per_page - 1) // per_page)

    offset = (page - 1) * per_page
    jobs = conn.execute(
        f"SELECT * FROM jobs WHERE {where_clause} ORDER BY {order_clause} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    return jobs, total, pages


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
