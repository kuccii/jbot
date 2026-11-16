"""Database cleanup — re-run eligibility, remove stale/bad data.

After updates to eligibility rules (e.g., bilingual filter), existing
jobs in the database may no longer qualify. This module:

1. Re-runs eligibility check on all stored jobs
2. Removes jobs that no longer pass updated rules
3. Cleans up stale data (jobs older than N days with status 'new')
4. Deduplicates by normalized title + company
5. Reclassify existing rows with audience routing (cleanup --reclassify)
"""

from __future__ import annotations

import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from job_hunter import eligibility, relevance
from job_hunter.config import Config
from job_hunter.models import Job, Store


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _row_to_job(row: sqlite3.Row) -> Job:
    """Convert a database row to a Job object for eligibility checking."""
    eligible_countries = row["eligible_countries"] if "eligible_countries" in row.keys() else ""
    if eligible_countries:
        eligible_countries = [c.strip() for c in eligible_countries.split(",") if c.strip()]
    else:
        eligible_countries = []

    return Job(
        title=row["title"] or "",
        company=row["company"] or "",
        url=row["url"] or "",
        board=row["board"] or "",
        location=row["location"] or "",
        remote=row["remote"] or "",
        tags=row["tags"] or "",
        description=row["description"] or "",
        posted_at=row["posted_at"] or "",
        eligible_countries=eligible_countries,
        audience=row["audience"] if "audience" in row.keys() else "",
    )


def recheck_eligibility(db_path: str) -> dict:
    """Re-run eligibility check on all jobs and remove ones that no longer qualify."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    jobs = conn.execute("SELECT * FROM jobs WHERE eligible=1").fetchall()
    _log(f"Rechecking eligibility for {len(jobs)} jobs...")

    removed = 0
    kept = 0
    reason_counts: dict[str, int] = {}

    for row in jobs:
        job = _row_to_job(row)
        if row["board"] == "visa_sponsorship":
            ok, note = eligibility.check_visa_sponsorship(job)
        else:
            ok, note = eligibility.check_eligibility(job)

        if not ok:
            conn.execute("DELETE FROM jobs WHERE id = ?", (row["id"],))
            removed += 1
            reason = note.split(":")[0] if ":" in note else note
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        else:
            kept += 1

    conn.commit()
    conn.close()

    return {
        "total": len(jobs),
        "kept": kept,
        "removed": removed,
        "reason_counts": reason_counts,
    }


def remove_stale(db_path: str, days: int = 30) -> int:
    """Remove jobs older than N days with status 'new' (never saved/applied)."""
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    cur = conn.execute(
        "DELETE FROM jobs WHERE status = 'new' AND found_at < ?",
        (cutoff,),
    )
    conn.commit()
    count = cur.rowcount
    conn.close()
    return count


def deduplicate(db_path: str) -> int:
    """Remove duplicate jobs (same normalized title + company), keeping the newest."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, title, company, found_at FROM jobs WHERE eligible=1 ORDER BY found_at DESC"
    ).fetchall()

    seen: dict[str, int] = {}
    to_delete: list[int] = []

    for row in rows:
        title = re.sub(r"[^a-z0-9 ]", " ", (row["title"] or "").lower()).strip()
        company = re.sub(r"[^a-z0-9 ]", " ", (row["company"] or "").lower()).strip()
        if not title or not company:
            continue
        key = f"{title}|{company}"
        if key in seen:
            to_delete.append(row["id"])
        else:
            seen[key] = row["id"]

    if to_delete:
        placeholders = ",".join("?" * len(to_delete))
        conn.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", to_delete)
        conn.commit()

    conn.close()
    return len(to_delete)


def full_cleanup(db_path: str, stale_days: int = 30) -> dict:
    """Run all cleanup steps."""
    _log("=== Full Cleanup ===")

    _log("\nStep 1: Re-checking eligibility...")
    eligibility_result = recheck_eligibility(db_path)
    _log(f"  Removed {eligibility_result['removed']} jobs that no longer qualify")
    if eligibility_result["reason_counts"]:
        for reason, count in sorted(eligibility_result["reason_counts"].items(), key=lambda x: -x[1]):
            _log(f"    {reason}: {count}")

    _log(f"\nStep 2: Removing jobs older than {stale_days} days...")
    stale_removed = remove_stale(db_path, stale_days)
    _log(f"  Removed {stale_removed} stale jobs")

    _log("\nStep 3: Removing duplicates...")
    dupes_removed = deduplicate(db_path)
    _log(f"  Removed {dupes_removed} duplicates")

    conn = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    eligible = conn.execute("SELECT COUNT(*) FROM jobs WHERE eligible=1").fetchone()[0]
    conn.close()

    _log(f"\nFinal: {total} total, {eligible} eligible")

    return {
        "eligibility_removed": eligibility_result["removed"],
        "eligibility_reasons": eligibility_result["reason_counts"],
        "stale_removed": stale_removed,
        "dupes_removed": dupes_removed,
        "final_total": total,
        "final_eligible": eligible,
    }


def reclassify(db_path: str, cfg=None) -> dict:
    """Re-derive audience/score for every row; delete only status='new' failures.

    History rows (applied/hidden/skipped) are re-scored but never deleted —
    failures are soft-marked eligible=0.
    """
    if cfg is None:
        cfg = Config()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("UPDATE jobs SET audience='entry' WHERE audience IN ('gig','creative')")
    rows = conn.execute("SELECT * FROM jobs").fetchall()
    stats = {"total": len(rows), "kept": 0, "removed": 0, "updated": 0, "reason_counts": {}}
    for row in rows:
        job = _row_to_job(row)
        cls = relevance.classify(job, cfg)
        if cls.audience is None:
            reason = cls.note.split(":")[0]
            stats["reason_counts"][reason] = stats["reason_counts"].get(reason, 0) + 1
            status = row["status"] if "status" in row.keys() else "new"
            if (status or "new") == "new":
                conn.execute("DELETE FROM jobs WHERE id=?", (row["id"],))
                stats["removed"] += 1
            else:
                conn.execute(
                    "UPDATE jobs SET eligible=0, eligibility_note=? WHERE id=?",
                    (f"[reclassified] {cls.note}", row["id"]),
                )
            continue
        conn.execute(
            "UPDATE jobs SET audience=?, score=?, score_reasons=?, eligible=1, eligibility_note=? WHERE id=?",
            (cls.audience, cls.score, cls.reasons, cls.note, row["id"]),
        )
        stats["kept"] += 1
        stats["updated"] += 1
    conn.commit()
    conn.close()
    return stats