"""Job Hunter Dashboard — FastAPI web app for browsing discovered jobs.

Run with:
    python -m job_hunter.dashboard.server

Or from CLI:
    job-hunter dashboard
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from job_hunter.config import load_config

app = FastAPI(title="Job Hunter Dashboard", version="1.0.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _get_db() -> sqlite3.Connection:
    """Get database connection."""
    cfg = load_config()
    conn = sqlite3.connect(cfg.database)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Dashboard home — stats overview."""
    conn = _get_db()
    try:
        stats = _get_stats(conn)
        recent = conn.execute(
            "SELECT * FROM jobs WHERE eligible=1 ORDER BY found_at DESC LIMIT 10"
        ).fetchall()
        return templates.TemplateResponse(request, "home.html", {
            "stats": stats,
            "recent": recent,
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
    sort: str = Query("found_at", help="found_at (newest) or score (best fit)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=5, le=100),
):
    """Job listing page with filters."""
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
        return templates.TemplateResponse(request, "detail.html", {
            "job": job,
        })
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
        platforms = conn.execute(
            "SELECT * FROM jobs WHERE board='gig_platforms' AND eligible=1 ORDER BY title"
        ).fetchall()
        ai_gigs = conn.execute(
            "SELECT * FROM jobs WHERE board='opentrain' AND eligible=1 ORDER BY found_at DESC LIMIT 20"
        ).fetchall()
        indeed_jobs = conn.execute(
            "SELECT * FROM jobs WHERE board='indeed' AND eligible=1 ORDER BY title LIMIT 30"
        ).fetchall()
        entry_platforms = conn.execute(
            "SELECT * FROM jobs WHERE board='entry_platforms' AND eligible=1 ORDER BY title"
        ).fetchall()
        workday_jobs = conn.execute(
            "SELECT * FROM jobs WHERE board='workday' AND eligible=1 ORDER BY found_at DESC LIMIT 20"
        ).fetchall()
        entry_jobs = conn.execute(
            "SELECT * FROM jobs WHERE eligible=1 AND audience='entry' ORDER BY found_at DESC LIMIT 30"
        ).fetchall()
        creative_jobs = conn.execute(
            "SELECT * FROM jobs WHERE eligible=1 AND audience='creative' ORDER BY found_at DESC LIMIT 30"
        ).fetchall()
        tech_jobs = conn.execute(
            "SELECT * FROM jobs WHERE eligible=1 AND audience='tech' ORDER BY found_at DESC LIMIT 30"
        ).fetchall()
        return templates.TemplateResponse(request, "platforms.html", {
            "platforms": platforms,
            "entry_platforms": entry_platforms,
            "workday_jobs": workday_jobs,
            "ai_gigs": ai_gigs,
            "indeed_jobs": indeed_jobs,
            "entry_jobs": entry_jobs,
            "creative_jobs": creative_jobs,
            "tech_jobs": tech_jobs,
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API endpoints (JSON)
# ---------------------------------------------------------------------------

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
    board: str = "",
    status: str = "",
    search: str = "",
    audience: str = "",
    sort: str = "found_at",
    page: int = 1,
    per_page: int = 25,
):
    """JSON job listing."""
    conn = _get_db()
    try:
        jobs, total, pages = _query_jobs(conn, board, status, search, audience, page, per_page, sort)
        return {
            "jobs": [dict(j) for j in jobs],
            "total": total,
            "page": page,
            "pages": pages,
        }
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

    # Jobs added per day (last 7 days)
    daily = [
        {"date": r["date"], "count": r["n"]}
        for r in conn.execute(
            """SELECT DATE(found_at) as date, COUNT(*) as n
               FROM jobs WHERE eligible=1
               GROUP BY DATE(found_at) ORDER BY date DESC LIMIT 7"""
        ).fetchall()
    ]

    return {
        "total": total,
        "eligible": eligible,
        "by_board": by_board,
        "by_status": by_status,
        "by_audience": by_audience,
        "daily": daily,
    }


def _query_jobs(
    conn: sqlite3.Connection,
    board: str,
    status: str,
    search: str,
    audience: str,
    page: int,
    per_page: int,
    sort: str = "found_at",
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
    order_clause = "score DESC, found_at DESC" if sort == "score" else "found_at DESC"

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
