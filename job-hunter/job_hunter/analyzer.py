"""Post-discovery job analyzer and refiner.

After discovery, this service:
1. Validates links — checks if URLs are still live
2. Analyzes quality — flags missing data, suspicious titles, duplicates
3. Refines — marks dead links, removes stale jobs, enriches data

Run via CLI: python -m job_hunter analyze
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx


@dataclass
class AnalysisResult:
    """Result of analyzing a single job."""
    job_id: int
    url: str
    title: str
    board: str
    issues: list[str] = field(default_factory=list)
    link_status: str = "unknown"  # live, dead, redirect, error
    quality_score: float = 1.0
    action: str = "keep"  # keep, remove, flag


@dataclass
class AnalysisSummary:
    """Summary of the full analysis."""
    total: int = 0
    live: int = 0
    dead: int = 0
    redirect: int = 0
    error: int = 0
    low_quality: int = 0
    duplicates: int = 0
    removed: int = 0
    flagged: int = 0
    results: list[AnalysisResult] = field(default_factory=list)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ─── Link Validator ────────────────────────────────────────────────────────

# Domains we skip during link checking (known live or bot-blocked)
_SKIP_DOMAINS = {
    "indeed.com", "indeed.co.uk", "indeed.de", "indeed.nl",
    "indeed.ie", "indeed.fr", "indeed.ca", "indeed.com.au",
    "indeed.sg", "indeed.co.in", "indeed.co.za", "indeed.be",
    "indeed.cz", "indeed.hu", "indeed.no", "indeed.fi",
    "indeed.pt", "indeed.es", "indeed.ch",
    "uk.indeed.com", "de.indeed.com",
}


def _should_skip(url: str) -> bool:
    """Check if URL domain should be skipped."""
    try:
        domain = urlparse(url).hostname or ""
        return any(domain.endswith(d) for d in _SKIP_DOMAINS)
    except Exception:
        return False


async def _check_batch(client: httpx.AsyncClient,
                       batch: list[tuple[int, str]]) -> list[tuple[int, str, int]]:
    """Check a batch of URLs concurrently. Returns [(job_id, status, code)]."""

    async def _check_one(job_id: int, url: str) -> tuple[int, str, int]:
        if _should_skip(url):
            return job_id, "live", 200
        try:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            })
            code = resp.status_code
            if code == 200:
                text = resp.text[:2000].lower()
                if "page not found" in text or "404" in text[:200]:
                    return job_id, "dead", code
                return job_id, "live", code
            elif 300 <= code < 400:
                return job_id, "redirect", code
            elif code in (403, 429):
                return job_id, "live", code  # Alive but blocks bots
            elif code == 404:
                return job_id, "dead", code
            elif code >= 500:
                return job_id, "error", code
            else:
                return job_id, "dead", code
        except Exception:
            return job_id, "error", 0

    tasks = [_check_one(jid, url) for jid, url in batch]
    return await asyncio.gather(*tasks)


# ─── Job Analyzer ──────────────────────────────────────────────────────────

SUSPICIOUS_PATTERNS = [
    r"general\s+application", r"talent\s+community",
    r"campus\s+crew", r"brand\s+ambassador",
    r"unpaid\s+intern", r"commission\s+only",
    r"guaranteed\s+income", r"make\s+money\s+fast",
]

QUALITY_SIGNALS = [
    "remote", "worldwide", "anywhere", "global",
    "full-time", "part-time", "contract", "visa sponsorship",
]


def _analyze_job_quality(row: sqlite3.Row) -> tuple[float, list[str]]:
    """Analyze job data quality. Returns (score, issues)."""
    score = 1.0
    issues = []

    title = (row["title"] or "").strip()
    company = (row["company"] or "").strip()
    description = (row["description"] or "").strip()
    url = (row["url"] or "").strip()

    if not title or len(title) < 5:
        score -= 0.3
        issues.append("title_too_short")
    if not company:
        score -= 0.1
        issues.append("missing_company")
    if not description or len(description) < 20:
        score -= 0.2
        issues.append("missing_description")
    if not url or not url.startswith("http"):
        score -= 0.5
        issues.append("invalid_url")

    title_lower = title.lower()
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, title_lower):
            score -= 0.4
            issues.append(f"suspicious_title")
            break

    if company and title:
        norm_title = re.sub(r"[^a-z0-9 ]", " ", title_lower).strip()
        if len(norm_title) < 10:
            score -= 0.1
            issues.append("generic_title")

    for signal in QUALITY_SIGNALS:
        if signal in title_lower or signal in description.lower():
            score = min(1.0, score + 0.05)

    return max(0.0, min(1.0, score)), issues


# ─── Duplicate Detection ───────────────────────────────────────────────────

def _find_duplicates(conn: sqlite3.Connection) -> list[tuple[int, int, str]]:
    """Find duplicate jobs (same title + company)."""
    duplicates = []
    rows = conn.execute(
        "SELECT id, title, company FROM jobs WHERE eligible=1 ORDER BY found_at DESC"
    ).fetchall()

    seen: dict[str, int] = {}
    for row in rows:
        title = re.sub(r"[^a-z0-9 ]", " ", (row["title"] or "").lower()).strip()
        company = re.sub(r"[^a-z0-9 ]", " ", (row["company"] or "").lower()).strip()
        if not title or not company:
            continue
        key = f"{title}|{company}"
        if key in seen:
            duplicates.append((seen[key], row["id"], f"duplicate_of_{seen[key]}"))
        else:
            seen[key] = row["id"]
    return duplicates


# ─── Main Analysis Pipeline ────────────────────────────────────────────────

async def analyze(db_path: str, check_links: bool = True,
                  batch_size: int = 20) -> AnalysisSummary:
    """Run full analysis on all jobs in the database.

    Uses a shared httpx client with concurrent batch checking for speed.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    summary = AnalysisSummary()

    jobs = conn.execute(
        "SELECT * FROM jobs WHERE eligible=1 ORDER BY found_at DESC"
    ).fetchall()
    summary.total = len(jobs)
    _log(f"Analyzing {summary.total} jobs...")

    # ── Step 1: Link Validation (concurrent batches with shared client) ──
    link_results: dict[int, tuple[str, int]] = {}

    if check_links:
        _log("Step 1: Validating links...")
        urls = [(row["id"], row["url"]) for row in jobs if row["url"]]

        async with httpx.AsyncClient(
            timeout=8.0, follow_redirects=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        ) as client:
            for i in range(0, len(urls), batch_size):
                batch = urls[i:i + batch_size]
                results = await _check_batch(client, batch)
                for job_id, status, code in results:
                    link_results[job_id] = (status, code)

                done = min(i + batch_size, len(urls))
                if done % 100 == 0 or done == len(urls):
                    _log(f"  Checked {done}/{len(urls)} URLs")

        for job_id, (status, code) in link_results.items():
            if status == "live":
                summary.live += 1
            elif status == "dead":
                summary.dead += 1
            elif status == "redirect":
                summary.redirect += 1
            else:
                summary.error += 1
    else:
        _log("Step 1: Skipping link validation")

    # ── Step 2: Quality Analysis ───────────────────────────────────────
    _log("Step 2: Analyzing quality...")
    for row in jobs:
        score, issues = _analyze_job_quality(row)
        link_status = link_results.get(row["id"], ("unknown", 0))[0] if check_links else "unknown"

        action = "keep"
        if link_status == "dead":
            action = "remove"
        elif score < 0.5:
            action = "flag"
            summary.low_quality += 1

        summary.results.append(AnalysisResult(
            job_id=row["id"], url=row["url"], title=row["title"],
            board=row["board"], issues=issues, link_status=link_status,
            quality_score=score, action=action,
        ))

    # ── Step 3: Duplicate Detection ────────────────────────────────────
    _log("Step 3: Detecting duplicates...")
    duplicates = _find_duplicates(conn)
    summary.duplicates = len(duplicates)

    for keep_id, remove_id, reason in duplicates:
        for r in summary.results:
            if r.job_id == remove_id:
                r.action = "remove"
                r.issues.append(reason)
                break

    # ── Step 4: Apply Actions ──────────────────────────────────────────
    _log("Step 4: Applying actions...")

    remove_ids = [r.job_id for r in summary.results if r.action == "remove"]
    if remove_ids:
        placeholders = ",".join("?" * len(remove_ids))
        cur = conn.execute(
            f"UPDATE jobs SET status='dead' WHERE id IN ({placeholders})",
            remove_ids,
        )
        summary.removed = cur.rowcount
        _log(f"  Marked {summary.removed} jobs as dead")

    flag_ids = [r.job_id for r in summary.results if r.action == "flag"]
    if flag_ids:
        placeholders = ",".join("?" * len(flag_ids))
        conn.execute(
            f"UPDATE jobs SET status='flagged' WHERE id IN ({placeholders}) AND status='new'",
            flag_ids,
        )
        summary.flagged = len(flag_ids)
        _log(f"  Flagged {summary.flagged} low-quality jobs")

    conn.commit()
    conn.close()
    return summary


def print_summary(summary: AnalysisSummary) -> None:
    """Print analysis summary."""
    print(f"\n{'='*60}")
    print(f"  Job Analysis Summary")
    print(f"{'='*60}")
    print(f"  Total analyzed:    {summary.total}")
    print(f"  Live links:        {summary.live}")
    print(f"  Dead links:        {summary.dead}")
    print(f"  Redirects:         {summary.redirect}")
    print(f"  Errors:            {summary.error}")
    print(f"  Low quality:       {summary.low_quality}")
    print(f"  Duplicates:        {summary.duplicates}")
    print(f"  ─────────────────────────")
    print(f"  Marked dead:       {summary.removed}")
    print(f"  Flagged:           {summary.flagged}")
    print(f"{'='*60}")

    issue_counts: dict[str, int] = {}
    for r in summary.results:
        for issue in r.issues:
            key = issue.split(":")[0]
            issue_counts[key] = issue_counts.get(key, 0) + 1

    if issue_counts:
        print(f"\n  Top Issues:")
        for issue, count in sorted(issue_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {issue:30s}: {count}")

    board_stats: dict[str, dict] = {}
    for r in summary.results:
        board = r.board
        if board not in board_stats:
            board_stats[board] = {"total": 0, "dead": 0, "flagged": 0}
        board_stats[board]["total"] += 1
        if r.action == "remove":
            board_stats[board]["dead"] += 1
        elif r.action == "flag":
            board_stats[board]["flagged"] += 1

    print(f"\n  Board Breakdown:")
    for board, stats in sorted(board_stats.items(), key=lambda x: -x[1]["total"]):
        dead_pct = (stats["dead"] / stats["total"] * 100) if stats["total"] else 0
        print(f"    {board:20s}: {stats['total']:4d} total, {stats['dead']:3d} dead ({dead_pct:.0f}%), {stats['flagged']:3d} flagged")
