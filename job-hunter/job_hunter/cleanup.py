"""Database cleanup — re-run eligibility, remove stale/bad data.

After updates to eligibility rules (e.g., bilingual filter), existing
jobs in the database may no longer qualify. This module:

1. Re-runs eligibility check on all stored jobs
2. Removes jobs that no longer pass updated rules
3. Cleans up stale data (jobs older than N days with status 'new')
4. Deduplicates by normalized title + company

Run via CLI: python -m job_hunter cleanup
"""

from __future__ import annotations

import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from job_hunter import eligibility
from job_hunter.models import Job, Store


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _row_to_job(row: sqlite3.Row) -> Job:
    """Convert a database row to a Job object for eligibility checking."""
    eligible_countries = row["eligible_countries"]
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
        audience=row["audience"] or "",
    )


def recheck_eligibility(db_path: str) -> dict:
    """Re-run eligibility check on all jobs and remove ones that no longer qualify.

    Returns stats: {total, kept, removed, reason_counts}
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    jobs = conn.execute("SELECT * FROM jobs WHERE eligible=1").fetchall()
    _log(f"Rechecking eligibility for {len(jobs)} jobs...")

    removed = 0
    kept = 0
    reason_counts: dict[str, int] = {}

    for row in jobs:
        job = _row_to_job(row)
        ok, note = eligibility.check_eligibility(job)

        if not ok:
            # Remove the job
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
    """Run all cleanup steps.

    Returns summary of all changes.
    """
    _log("=== Full Cleanup ===")

    # Step 1: Re-check eligibility
    _log("\nStep 1: Re-checking eligibility...")
    eligibility_result = recheck_eligibility(db_path)
    _log(f"  Removed {eligibility_result['removed']} jobs that no longer qualify")
    if eligibility_result["reason_counts"]:
        for reason, count in sorted(eligibility_result["reason_counts"].items(), key=lambda x: -x[1]):
            _log(f"    {reason}: {count}")

    # Step 2: Remove stale jobs
    _log(f"\nStep 2: Removing jobs older than {stale_days} days...")
    stale_removed = remove_stale(db_path, stale_days)
    _log(f"  Removed {stale_removed} stale jobs")

    # Step 3: Deduplicate
    _log("\nStep 3: Removing duplicates...")
    dupes_removed = deduplicate(db_path)
    _log(f"  Removed {dupes_removed} duplicates")

    # Final stats
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
