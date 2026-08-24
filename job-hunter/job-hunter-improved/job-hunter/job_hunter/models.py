"""Data model + SQLite storage for job-hunter.

Uses only the standard library — no ORM, keeps the project clean.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _norm_key(text: str) -> str:
    """Normalize a string for cross-board duplicate matching.

    Lowercases, strips punctuation, and collapses whitespace so
    "Senior, AI Engineer (Remote)" and "senior AI engineer remote" match.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


@dataclass
class Job:
    title: str
    company: str
    url: str
    board: str
    location: str = ""
    remote: str = ""
    tags: str = ""
    description: str = ""
    posted_at: str = ""
    # Countries explicitly listed as eligible (e.g. Remote4Africa).
    eligible_countries: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "board": self.board,
            "location": self.location,
            "remote": self.remote,
            "tags": self.tags,
            "description": self.description,
            "posted_at": self.posted_at,
            "eligible_countries": ",".join(self.eligible_countries),
        }


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    board TEXT NOT NULL,
    location TEXT DEFAULT '',
    remote TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    description TEXT DEFAULT '',
    posted_at TEXT DEFAULT '',
    eligible_countries TEXT DEFAULT '',
    eligible INTEGER DEFAULT 0,
    eligibility_note TEXT DEFAULT '',
    status TEXT DEFAULT 'new',
    score INTEGER DEFAULT 0,
    score_reasons TEXT DEFAULT '',
    notified INTEGER DEFAULT 0,
    found_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_jobs_board ON jobs(board);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS ix_jobs_score ON jobs(score);
CREATE INDEX IF NOT EXISTS ix_jobs_notified ON jobs(notified);
"""

# Columns added after the initial release. Applied with ALTER TABLE so
# existing databases upgrade in place instead of erroring on missing columns.
_MIGRATIONS: list[str] = [
    "ALTER TABLE jobs ADD COLUMN score INTEGER DEFAULT 0",
    "ALTER TABLE jobs ADD COLUMN score_reasons TEXT DEFAULT ''",
    "ALTER TABLE jobs ADD COLUMN notified INTEGER DEFAULT 0",
]


class Store:
    def __init__(self, db_path: str):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Add any columns missing from an older database file."""
        existing = {r["name"] for r in self.conn.execute("PRAGMA table_info(jobs)")}
        for stmt in _MIGRATIONS:
            col = stmt.split("ADD COLUMN")[1].split()[0]
            if col not in existing:
                self.conn.execute(stmt)
        self.conn.commit()

    def add_job(self, job: Job, eligible: bool, note: str,
                score: int = 0, score_reasons: str = "") -> str:
        """Insert if new. Returns 'new', 'exists', or 'duplicate'.

        'exists'  — the exact URL was already stored (same board re-fetch).
        'duplicate' — a job with the same normalized title + company was
        already stored from another board (cross-board dedup). Same-company
        postings of genuinely different roles survive because the title key
        differs. Jobs with no company name skip the cross-board check.
        """
        cur = self.conn.execute(
            "SELECT id FROM jobs WHERE url = ?", (job.url,)
        )
        if cur.fetchone():
            return "exists"

        if job.company.strip():
            n_title = _norm_key(job.title)
            n_company = _norm_key(job.company)
            for row in self.conn.execute(
                "SELECT title, company FROM jobs WHERE lower(company) = lower(?)",
                (job.company,),
            ):
                if (
                    _norm_key(row["title"]) == n_title
                    and _norm_key(row["company"]) == n_company
                ):
                    return "duplicate"

        self.conn.execute(
            """INSERT INTO jobs
               (title, company, url, board, location, remote, tags, description,
                posted_at, eligible_countries, eligible, eligibility_note, status,
                score, score_reasons, notified, found_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job.title, job.company, job.url, job.board, job.location,
                job.remote, job.tags, job.description, job.posted_at,
                ",".join(job.eligible_countries),
                1 if eligible else 0, note, "new",
                score, score_reasons, 0,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        return "new"

    def get_job(self, job_id: int) -> sqlite3.Row | None:
        """Fetch a single job by id, or None if it doesn't exist."""
        return self.conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

    def search(self, query: str, board: str | None = None,
               eligible_only: bool = True, limit: int = 30) -> list[sqlite3.Row]:
        """Search jobs by keyword across title, company, and description."""
        clauses = ["(title LIKE ? OR company LIKE ? OR description LIKE ?)"]
        q = f"%{query}%"
        params: list = [q, q, q]
        if eligible_only:
            clauses.append("eligible = 1")
        if board:
            clauses.append("board = ?")
            params.append(board)
        query_sql = "SELECT * FROM jobs WHERE " + " AND ".join(clauses)
        query_sql += " ORDER BY score DESC, found_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query_sql, params).fetchall()

    def set_score(self, job_id: int, score: int, reasons: str) -> None:
        self.conn.execute(
            "UPDATE jobs SET score = ?, score_reasons = ? WHERE id = ?",
            (score, reasons, job_id),
        )
        self.conn.commit()

    def unnotified(self, limit: int = 200) -> list[sqlite3.Row]:
        """Eligible jobs that haven't been sent in a notification digest yet."""
        return self.conn.execute(
            """SELECT * FROM jobs WHERE eligible = 1 AND notified = 0
               ORDER BY score DESC, found_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    def mark_notified(self, job_ids: list[int]) -> None:
        if not job_ids:
            return
        placeholders = ",".join("?" for _ in job_ids)
        self.conn.execute(
            f"UPDATE jobs SET notified = 1 WHERE id IN ({placeholders})", job_ids
        )
        self.conn.commit()

    def list_jobs(self, board: str | None = None, eligible_only: bool = True,
                  status: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
        query = "SELECT * FROM jobs"
        clauses, params = [], []
        if eligible_only:
            clauses.append("eligible = 1")
        if board:
            clauses.append("board = ?")
            params.append(board)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY score DESC, found_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchall()

    def stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        eligible = self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE eligible = 1"
        ).fetchone()[0]
        by_board = {
            r["board"]: r["n"]
            for r in self.conn.execute(
                "SELECT board, COUNT(*) AS n FROM jobs GROUP BY board ORDER BY n DESC"
            )
        }
        return {"total": total, "eligible": eligible, "by_board": by_board}

    def mark(self, job_id: int, status: str) -> bool:
        cur = self.conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?", (status, job_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def purge(self, status: str = "hidden") -> int:
        cur = self.conn.execute("DELETE FROM jobs WHERE status = ?", (status,))
        self.conn.commit()
        return cur.rowcount
