import sqlite3
c = sqlite3.connect("data/job_bot.db").cursor()

print("=== Source distribution (non-dead) ===")
for r in c.execute("SELECT source, COUNT() as cnt FROM opportunities WHERE status != 'dead' GROUP BY source ORDER BY cnt DESC"):
    print(f"  {r[0]:25s} {r[1]}")

print("\n=== Google search companies ===")
for r in c.execute("SELECT company, COUNT() FROM opportunities WHERE source='google_search' AND status != 'dead' GROUP BY company ORDER BY COUNT() DESC LIMIT 20"):
    print(f"  {str(r[0])[:35]:35s} x{r[1]}")

print("\n=== Recent google_search entries ===")
for r in c.execute("SELECT id, title, company, url FROM opportunities WHERE source='google_search' AND status != 'dead' ORDER BY id DESC LIMIT 10"):
    print(f"  [{r[0]}] {str(r[1])[:60]:60s} | {str(r[2])[:25]:25s} | {str(r[3])[:60]}")

print("\n=== Recent grants entries ===")
for r in c.execute("SELECT id, title, company, url FROM opportunities WHERE source='grants' AND status != 'dead' ORDER BY id DESC LIMIT 10"):
    print(f"  [{r[0]}] {str(r[1])[:60]:60s} | {str(r[2])[:25]:25s} | {str(r[3])[:60]}")

print("\n=== Recent company_pages entries ===")
for r in c.execute("SELECT id, title, company, url FROM opportunities WHERE source='company_pages' AND status != 'dead' ORDER BY id DESC LIMIT 10"):
    print(f"  [{r[0]}] {str(r[1])[:60]:60s} | {str(r[2])[:25]:25s} | {str(r[3])[:60]}")

print("\n=== Recent greenhouse_ats entries ===")
for r in c.execute("SELECT id, title, company, url FROM opportunities WHERE source='greenhouse_ats' AND status != 'dead' ORDER BY id DESC LIMIT 10"):
    print(f"  [{r[0]}] {str(r[1])[:60]:60s} | {str(r[2])[:25]:25s} | {str(r[3])[:60]}")
