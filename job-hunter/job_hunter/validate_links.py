"""Validate all job URLs in the database.

For each URL:
1. HEAD request (fast) → check if live
2. If HEAD fails, try GET with short timeout
3. Record: status code, redirect chain, final URL, response time
"""

import asyncio
import sqlite3
import time
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Concurrency limit to avoid hammering
MAX_CONCURRENT = 20


async def check_url(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore) -> dict:
    """Check a single URL and return status info."""
    result = {"url": url, "status": 0, "final_url": url, "ok": False, "error": "", "redirect": False, "ms": 0}

    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        result["url"] = url

    async with sem:
        t0 = time.monotonic()
        try:
            # Try HEAD first (fast)
            resp = await client.head(url, follow_redirects=True, timeout=12.0)
            result["status"] = resp.status_code
            result["final_url"] = str(resp.url)
            result["redirect"] = str(resp.url) != url
            result["ok"] = resp.status_code < 400
            result["ms"] = round((time.monotonic() - t0) * 1000)
        except Exception:
            try:
                # Fallback to GET
                t1 = time.monotonic()
                resp = await client.get(url, follow_redirects=True, timeout=12.0)
                result["status"] = resp.status_code
                result["final_url"] = str(resp.url)
                result["redirect"] = str(resp.url) != url
                result["ok"] = resp.status_code < 400
                result["ms"] = round((time.monotonic() - t1) * 1000)
            except httpx.TimeoutException:
                result["error"] = "timeout"
                result["ms"] = round((time.monotonic() - t0) * 1000)
            except Exception as e:
                result["error"] = type(e).__name__
                result["ms"] = round((time.monotonic() - t0) * 1000)

    return result


async def validate_all():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, title, company, board, url FROM jobs WHERE eligible=1 AND url != '' ORDER BY board"
    ).fetchall()

    total = len(rows)
    print(f"Validating {total} URLs...")

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results = []

    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        tasks = []
        for r in rows:
            tasks.append(check_url(client, r["url"], sem))
            # Also store metadata
            tasks[-1] = (tasks[-1], r["id"], r["board"], r["title"][:50])

        # Run in batches of 50
        batch_size = 50
        done = 0
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            coros = [t[0] for t in batch]
            batch_results = await asyncio.gather(*coros)
            for j, res in enumerate(batch_results):
                meta = batch[j][1:]
                results.append({**res, "id": meta[0], "board": meta[1], "title": meta[2]})
            done += len(batch_results)
            print(f"  Checked {done}/{total}...", end="\r")

    conn.close()
    return results


def analyze(results: list[dict]):
    """Analyze results and produce a report."""
    # Categorize
    working = [r for r in results if r["ok"]]
    dead = [r for r in results if not r["ok"] and r["error"] in ("timeout", "ConnectError", "ConnectionError")]
    blocked = [r for r in results if not r["ok"] and r["status"] in (403, 429)]
    not_found = [r for r in results if not r["ok"] and r["status"] == 404]
    server_error = [r for r in results if not r["ok"] and 500 <= r["status"] < 600]
    other_fail = [r for r in results if not r["ok"] and r["status"] not in (403, 404, 429) and 500 > r["status"] >= 400]

    print(f"\n{'='*80}")
    print(f"  URL VALIDATION REPORT — {len(results)} total links")
    print(f"{'='*80}")
    print(f"\n  ✅ Working:    {len(working):>5} ({len(working)*100//len(results)}%)")
    print(f"  ❌ Dead/Timeout: {len(dead):>5}")
    print(f"  🚫 Blocked (403/429): {len(blocked):>5}")
    print(f"  ❓ Not Found (404): {len(not_found):>5}")
    print(f"  💥 Server Error: {len(server_error):>5}")
    print(f"  ⚠️  Other (4xx): {len(other_fail):>5}")

    # Per-board breakdown
    print(f"\n{'─'*80}")
    print(f"  PER-BOARD BREAKDOWN")
    print(f"{'─'*80}")

    by_board = defaultdict(lambda: {"total": 0, "working": 0, "dead": 0, "blocked": 0, "not_found": 0, "server_error": 0})
    for r in results:
        b = r["board"]
        by_board[b]["total"] += 1
        if r["ok"]:
            by_board[b]["working"] += 1
        elif r["error"] in ("timeout", "ConnectError", "ConnectionError"):
            by_board[b]["dead"] += 1
        elif r["status"] in (403, 429):
            by_board[b]["blocked"] += 1
        elif r["status"] == 404:
            by_board[b]["not_found"] += 1
        elif 500 <= r["status"] < 600:
            by_board[b]["server_error"] += 1

    print(f"  {'Board':<20} {'Total':>6} {'✅ OK':>6} {'❌ Dead':>7} {'🚫 Block':>8} {'❓ 404':>6} {'💥 5xx':>6}  Verdict")
    print(f"  {'─'*20} {'─'*6} {'─'*6} {'─'*7} {'─'*8} {'─'*6} {'─'*6}  {'─'*20}")

    for board, stats in sorted(by_board.items(), key=lambda x: -x[1]["total"]):
        pct = stats["working"] * 100 // max(stats["total"], 1)
        if pct >= 80:
            verdict = "🟢 HIGH VALUE"
        elif pct >= 50:
            verdict = "🟡 MIXED"
        elif pct >= 20:
            verdict = "🟠 LOW VALUE"
        else:
            verdict = "🔴 BROKEN"

        print(f"  {board:<20} {stats['total']:>6} {stats['working']:>6} {stats['dead']:>7} {stats['blocked']:>8} {stats['not_found']:>6} {stats['server_error']:>6}  {verdict}")

    # Show specific dead/blocked URLs per board (sample)
    print(f"\n{'─'*80}")
    print(f"  SAMPLE PROBLEM URLs")
    print(f"{'─'*80}")

    problem_boards = {}
    for r in results:
        if not r["ok"]:
            b = r["board"]
            if b not in problem_boards:
                problem_boards[b] = []
            if len(problem_boards[b]) < 3:
                reason = r["error"] or f"HTTP {r['status']}"
                problem_boards[b].append(f"    [{r['id']}] {r['title'][:40]} → {reason}")

    for board, issues in sorted(problem_boards.items()):
        print(f"\n  {board}:")
        for issue in issues:
            print(issue)

    # Overall verdict
    print(f"\n{'='*80}")
    print(f"  VERDICT")
    print(f"{'='*80}")

    high_value = [b for b, s in by_board.items() if s["working"] * 100 // max(s["total"], 1) >= 80]
    mixed = [b for b, s in by_board.items() if 50 <= s["working"] * 100 // max(s["total"], 1) < 80]
    broken = [b for b, s in by_board.items() if s["working"] * 100 // max(s["total"], 1) < 50]

    print(f"\n  🟢 KEEP ({len(high_value)} boards): {', '.join(high_value)}")
    print(f"  🟡 REVIEW ({len(mixed)} boards): {', '.join(mixed)}")
    print(f"  🔴 DROP/REBUILD ({len(broken)} boards): {', '.join(broken)}")

    overall = len(working) * 100 // len(results) if results else 0
    print(f"\n  Overall link health: {overall}%")
    if overall >= 70:
        print(f"  ➜ Data quality is GOOD. Most links are valid.")
    elif overall >= 40:
        print(f"  ➜ Data quality is MIXED. Some boards need rebuilding.")
    else:
        print(f"  ➜ Data quality is POOR. Most links are dead. Full re-scrape needed.")

    return {
        "total": len(results),
        "working": len(working),
        "dead": len(dead),
        "blocked": len(blocked),
        "not_found": len(not_found),
        "server_error": len(server_error),
        "by_board": dict(by_board),
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    results = asyncio.run(validate_all())
    report = analyze(results)

    # Save raw results
    out = Path(__file__).parent.parent / "link_check.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Raw results saved to {out}")
