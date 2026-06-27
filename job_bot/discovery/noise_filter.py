"""Comprehensive noise filter for discovery data.

Checks all scrapped opportunities against known noise patterns
and purges them. Can run as a CLI script or be imported for
startup cleanup.
"""

import re
import sqlite3
from pathlib import Path
from typing import Optional

AGGREGATOR_DOMAINS = [
    "remotive.com", "remoteok.com", "weworkremotely.com",
    "remotejobsafrica.com", "remotecareer.africa", "remoteli.com",
    "upwork.com", "toptal.com", "freelancer.com", "fiverr.com",
    "workana.com", "peopleperhour.com", "progigfinder.com",
    "indeed.com", "ziprecruiter.com", "monster.com", "simplyhired.com",
    "glassdoor.com", "careerbuilder.com", "flexjobs.com",
    "dynamitejobs.com", "remoterocketship.com", "remote4africa.com",
    "crossover.com", "seganrecruitment.com", "careerhound.io", "fuzu.com",
    "globalhire360.com", "jobgether.com",
    "tunga.io", "gebeya.com",
    "arc.dev", "mctaba.com",
    "youtube.com", "youtu.be", "substack.com",
    "wellfound.com",
    "himalayas.app", "rubyonremote.com",
    "reddit.com", "remote.co", "nodesk.co",
    "remoteafrica.io",
    "jobviewtrack.com",
    "linkedin.com",
    "workingnomads.com", "4dayweek.io",
    "instagram.com", "facebook.com", "tiktok.com",
    "grantwriting.ca", "instrumentl.com",
    "researchbunny.com", "peopleinai.com",
    # Aggregator / meta-roundup sites that don't list actual jobs
    "opportunitiesforafricans.com", "opportunitydesk.org",
    "invest-for-jobs.com", "menterprise.africa",
    "fundsforngos.org",
    "anzishaprize.org", "mastercardfoundation.org",
]

TWITTER_PROFILE_PATTERNS = [
    r"^/@?\w+",           # "/username" or "/@username"
    r"/posts/\s*$",        # profile /posts page
    r"/with_replies\s*$",  # profile /with_replies page
    r"/media\s*$",         # profile /media page
    r"/likes\s*$",         # profile /likes page
]

NOISE_SOURCES = {"twitter"}


def _url_matches_domain(url: str, domains: list[str]) -> bool:
    url_lower = url.lower()
    return any(d in url_lower for d in domains)


def _is_twitter_profile(url: str) -> bool:
    """Check if URL is a Twitter/X profile page, not a tweet."""
    path = url.split("?")[0].rstrip("/")
    # Profile pages: /username (single segment after twitter.com/)
    # Tweet URLs: /username/status/12345
    for pat in TWITTER_PROFILE_PATTERNS:
        if re.search(pat, path):
            return True
    # Check if it's a profile (single path segment after domain)
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
    """True if google_search entry has no real company (aggregator scrape)."""
    if not company or not company.strip():
        return True
    company_lower = company.lower().strip()
    if any(d in company_lower for d in ("google", "youtube")):
        return False
    if len(company_lower) < 2:
        return True
    # If company name itself is an aggregator
    if any(d in company_lower for d in ("linkedin", "twitter", "reddit", "wellfound")):
        return True
    return _url_matches_domain(url, AGGREGATOR_DOMAINS)


def check_entry(source: str, url: str, company: Optional[str], title: str) -> Optional[str]:
    """Returns reason string if entry is noise, None if clean."""
    url = url or ""
    company = company or ""
    title = title or ""

    if source in NOISE_SOURCES:
        return f"source '{source}' is pure noise"

    if _url_matches_domain(url, AGGREGATOR_DOMAINS):
        return f"URL contains aggregator domain"

    # Check if company name matches aggregator domain (for company_pages)
    company_lower = company.lower().strip()
    if _url_matches_domain(company_lower, AGGREGATOR_DOMAINS):
        return f"company matches aggregator domain"

    if _is_twitter_profile(url):
        return "twitter profile page (not a job tweet)"

    if source == "google_search" and _google_search_aggregator_only(company, url):
        return "google_search without identifiable company"

    if url.lower().endswith(".pdf"):
        return "PDF file (not an opportunity listing)"

    return None


def purge_noise(db_path: str, dry_run: bool = True) -> dict:
    """Scan all opportunities and purge/flag noise entries.

    Args:
        db_path: Path to SQLite database.
        dry_run: If True, only report without modifying.

    Returns:
        dict with summary stats.
    """
    if not Path(db_path).exists():
        return {"error": f"Database not found: {db_path}"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        "SELECT id, source, url, company, title, status FROM opportunities"
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
