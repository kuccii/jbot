"""Comprehensive noise filter for discovery data.

Checks all scrapped opportunities against known noise patterns
and purges them. Can run as a CLI script or be imported for
startup cleanup.
"""

import re
import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime

from job_bot.discovery.aggregator_domains import AGGREGATOR_DOMAINS

TWITTER_PROFILE_PATTERNS = [
    r"^/@?\w+",
    r"/posts/\s*$",
    r"/with_replies\s*$",
    r"/media\s*$",
    r"/likes\s*$",
]

NOISE_SOURCES = {"twitter"}

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 12, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

DEADLINE_PATTERNS = [
    re.compile(r"(?:deadline|due\s*date|closes|apply\s*by)\s*:?\s*(\d{1,2})(?:st|nd|rd|th)?\s*(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*,?\s*(\d{4})", re.IGNORECASE),
    re.compile(r"(?:deadline|due\s*date|closes|apply\s*by)\s*:?\s*(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})", re.IGNORECASE),
]


def _url_matches_domain(url: str, domains: list[str]) -> bool:
    url_lower = url.lower()
    return any(d in url_lower for d in domains)


def _is_twitter_profile(url: str) -> bool:
    path = url.split("?")[0].rstrip("/")
    for pat in TWITTER_PROFILE_PATTERNS:
        if re.search(pat, path):
            return True
    url_lower = url.lower()
    if not any(d in url_lower for d in ("twitter.com", "x.com", "t.co")):
        return False
    domain_stripped = path.split("twitter.com")[-1].split("x.com")[-1]
    segments = [s for s in domain_stripped.split("/") if s]
    if len(segments) <= 1:
        return True
    if len(segments) >= 2 and segments[1] not in ("status", "tweets"):
        return True
    return False


def _google_search_aggregator_only(company: Optional[str], url: str) -> bool:
    if not company or not company.strip():
        return True
    company_lower = company.lower().strip()
    if any(d in company_lower for d in ("google", "youtube")):
        return False
    if len(company_lower) < 2:
        return True
    if any(d in company_lower for d in ("linkedin", "twitter", "reddit", "wellfound")):
        return True
    return _url_matches_domain(url, AGGREGATOR_DOMAINS)


def _extract_deadline(text: str) -> Optional[str]:
    """Try to extract a deadline date from text. Returns 'YYYY-MM-DD' or None."""
    if not text:
        return None
    for pat in DEADLINE_PATTERNS:
        m = pat.search(text)
        if m:
            groups = m.groups()
            if groups[0].isalpha():
                month_str, day_str, year_str = groups
            else:
                day_str, month_str, year_str = groups
            month = MONTH_MAP.get(month_str.lower()[:3])
            if month:
                day = int(re.sub(r"[^\d]", "", day_str))
                year = int(re.sub(r"[^\d]", "", year_str))
                if 1 <= day <= 31 and 2020 <= year <= 2030:
                    return f"{year}-{month:02d}-{day:02d}"
    return None


def _is_expired_by_deadline(deadline_str: Optional[str], description: str) -> bool:
    """Check if a deadline date found in description has already passed."""
    d = _extract_deadline(description)
    if not d:
        return False
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return dt < datetime.now()
    except ValueError:
        return False


def check_entry(source: str, url: str, company: Optional[str], title: str, description: str = "") -> Optional[str]:
    """Returns reason string if entry is noise, None if clean."""
    url = url or ""
    company = company or ""
    title = title or ""
    description = description or ""

    if source in NOISE_SOURCES:
        return f"source '{source}' is pure noise"

    if _url_matches_domain(url, AGGREGATOR_DOMAINS):
        return "URL contains aggregator domain"

    company_lower = company.lower().strip()
    if _url_matches_domain(company_lower, AGGREGATOR_DOMAINS):
        return "company matches aggregator domain"

    if _is_twitter_profile(url):
        return "twitter profile page (not a job tweet)"

    if source == "google_search" and _google_search_aggregator_only(company, url):
        return "google_search without identifiable company"

    if url.lower().endswith(".pdf"):
        return "PDF file (not an opportunity listing)"

    current_year = datetime.now().year
    combined = title + " " + company
    for y in range(2010, current_year - 1):
        s = str(y)
        if s in combined:
            return f"expired ({s})"

    if _is_expired_by_deadline(None, description):
        return "deadline has passed"

    return None


def purge_noise(db_path: str, dry_run: bool = True) -> dict:
    """Scan all opportunities and purge/flag noise entries."""
    if not Path(db_path).exists():
        return {"error": f"Database not found: {db_path}"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        "SELECT id, source, url, company, title, description, status FROM opportunities"
    ).fetchall()

    stats = {
        "total": len(rows),
        "removed": 0,
        "already_dead": 0,
        "by_reason": {},
        "samples": [],
    }

    for row in rows:
        if row["status"] == "dead":
            stats["already_dead"] += 1
            continue

        reason = check_entry(
            source=row["source"],
            url=row["url"] or "",
            company=row["company"],
            title=row["title"],
            description=row["description"] or "",
        )
        if reason:
            stats["removed"] += 1
            stats["by_reason"][reason] = stats["by_reason"].get(reason, 0) + 1
            if len(stats["samples"]) < 5:
                stats["samples"].append({
                    "id": row["id"],
                    "title": row["title"][:80],
                    "source": row["source"],
                    "url": row["url"],
                    "reason": reason,
                })
            if not dry_run:
                cur.execute(
                    "UPDATE opportunities SET status = 'dead', liveness_status = 'dead' WHERE id = ?",
                    (row["id"],),
                )

    if not dry_run:
        conn.commit()

    conn.close()
    stats["dry_run"] = dry_run
    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Purge noise from JBot database")
    parser.add_argument("--db", default="data/job_bot.db", help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Preview without modifying")
    parser.add_argument("--apply", action="store_true", help="Actually purge (mark dead)")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.apply
    stats = purge_noise(args.db, dry_run=dry_run)

    if "error" in stats:
        print(f"Error: {stats['error']}")
        return

    print(f"Total entries: {stats['total']}")
    print(f"Already dead:  {stats['already_dead']}")
    print(f"Noise found:   {stats['removed']}")
    if stats["removed"]:
        print(f"\nBy reason:")
        for reason, count in sorted(stats["by_reason"].items(), key=lambda x: -x[1]):
            print(f"  {count:4d}  {reason}")
        print(f"\nSamples:")
        for s in stats["samples"]:
            print(f"  ID={s['id']} [{s['source']}] {s['title']}")
            print(f"      reason: {s['reason']}")
    if dry_run and stats["removed"]:
        print(f"\n[DRY RUN] Re-run with --apply to actually mark these as dead.")


if __name__ == "__main__":
    main()
