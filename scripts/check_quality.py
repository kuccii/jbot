import sqlite3, sys

conn = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else "data/job_bot.db")
cur = conn.cursor()

print("=== Source distribution (non-dead) ===")
for row in cur.execute("SELECT source, COUNT(*) as cnt FROM opportunities WHERE status != 'dead' GROUP BY source ORDER BY cnt DESC"):
    print(f"  {row[0]:25s} {row[1]}")

print("\n=== Recent entries by type ===")
for source in ["google_search", "greenhouse_ats", "company_pages", "grants"]:
    rows = cur.execute("SELECT id, title, company, url FROM opportunities WHERE source=? AND status != 'dead' ORDER BY id DESC LIMIT 5", (source,)).fetchall()
    if rows:
        print(f"\n--- {source} (last 5) ---")
        for r in rows:
            print(f"  [{r[0]}] {r[1][:70]:70s} | {r[2][:30]:30s} | {r[3][:80]}")

print("\n=== Companies that look like aggregators (google_search) ===")
rows = cur.execute("SELECT DISTINCT company, COUNT(*) FROM opportunities WHERE source='google_search' AND status != 'dead' GROUP BY company ORDER BY COUNT(*) DESC LIMIT 30").fetchall()
for r in rows:
    print(f"  {r[0]:30s} x{r[1]}")

print("\n=== Location distribution ===")
for row in cur.execute("SELECT location, COUNT(*) FROM opportunities WHERE location != '' AND location IS NOT NULL AND status != 'dead' GROUP BY location ORDER BY COUNT(*) DESC LIMIT 20"):
    print(f"  {row[0]:30s} x{row[1]}")

conn.close()
