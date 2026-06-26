"""One-time data repair script for JBot.

Fixes:
1. Re-categorize google_search records with grant/funding keywords
2. Deduplicate by normalized title
3. Mark broken twitter URLs as dead
4. Migrate schema (add new columns)

Usage: python scripts/repair_data.py [--db data/job_bot.db] [--dry-run]
"""
import argparse
import re
import sqlite3
from pathlib import Path


GRANT_KEYWORDS = ("grant", "funding", "fellowship", "scholarship", "award")
STARTUP_KEYWORDS = ("startup", "accelerator", "incubator", "venture", "pitch")


def normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t[:100]


def repair_categories(conn: sqlite3.Connection, dry_run: bool):
    rows = conn.execute(
        "SELECT id, title, description FROM opportunities WHERE source = 'google_search' AND category = 'job'"
    ).fetchall()
    fixed = 0
    for row in rows:
        text = (row[1] + " " + (row[2] or "")).lower()
        if any(w in text for w in GRANT_KEYWORDS):
            new_cat = "grant"
        elif any(w in text for w in STARTUP_KEYWORDS):
            new_cat = "startup"
        else:
            continue
        if not dry_run:
            conn.execute("UPDATE opportunities SET category = ? WHERE id = ?", (new_cat, row[0]))
        fixed += 1
    conn.commit()
    print(f"repaired categories: {fixed} records")


def deduplicate_titles(conn: sqlite3.Connection, dry_run: bool):
    rows = conn.execute(
        "SELECT id, title FROM opportunities ORDER BY created_at DESC"
    ).fetchall()
    seen = {}
    deduped = 0
    for row in rows:
        norm = normalize_title(row[1])
        if norm in seen:
            if not dry_run:
                conn.execute("UPDATE opportunities SET status = 'dead' WHERE id = ?", (row[0],))
            deduped += 1
        else:
            seen[norm] = row[0]
    conn.commit()
    print(f"deduplicated titles: {deduped} records marked dead")


def clean_twitter(conn: sqlite3.Connection, dry_run: bool):
    rows = conn.execute(
        "SELECT id, url FROM opportunities WHERE source = 'twitter'"
    ).fetchall()
    cleaned = 0
    for row in rows:
        url = (row[1] or "").lower()
        if not any(d in url for d in ("twitter.com", "x.com", "t.co")):
            if not dry_run:
                conn.execute("UPDATE opportunities SET status = 'dead' WHERE id = ?", (row[0],))
            cleaned += 1
    conn.commit()
    print(f"cleaned twitter: {cleaned} non-twitter URLs marked dead")


def migrate_schema(conn: sqlite3.Connection, dry_run: bool):
    existing = {row[1] for row in conn.execute("PRAGMA table_info('opportunities')").fetchall()}
    new_cols = {
        "liveness_checked_at": "DATETIME",
        "liveness_status": "VARCHAR(20)",
        "score_cv_match": "FLOAT",
        "score_compensation": "FLOAT",
        "score_culture": "FLOAT",
        "score_red_flags": "FLOAT",
        "score_legitimacy": "FLOAT",
        "score_global": "FLOAT",
        "score_prose": "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in existing:
            if dry_run:
                print(f"would add column: {col} {col_type}")
            else:
                conn.execute(f"ALTER TABLE opportunities ADD COLUMN {col} {col_type}")
                print(f"added column: {col} {col_type}")
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Repair JBot database")
    parser.add_argument("--db", default="data/job_bot.db", help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    if args.dry_run:
        print("=== DRY RUN ===")

    print("--- Migrating schema ---")
    migrate_schema(conn, args.dry_run)
    print("--- Repairing categories ---")
    repair_categories(conn, args.dry_run)
    print("--- Deduplicating titles ---")
    deduplicate_titles(conn, args.dry_run)
    print("--- Cleaning twitter ---")
    clean_twitter(conn, args.dry_run)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
