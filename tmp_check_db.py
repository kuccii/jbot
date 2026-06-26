import sqlite3
conn = sqlite3.connect('/root/JBot/data/job_bot.db')
cur = conn.cursor()

print('=== DUPLICATE URLS ===')
cur.execute('SELECT url, COUNT(*) as cnt FROM opportunities WHERE url IS NOT NULL AND url != \'\' GROUP BY url HAVING cnt > 1')
dups = cur.fetchall()
print(f'{len(dups)} duplicate URLs found')
for url, cnt in dups[:20]:
    cur.execute('SELECT id, title, source, category FROM opportunities WHERE url = ?', (url,))
    rows = cur.fetchall()
    ids = [str(r[0]) for r in rows]
    print(f'  URL: {url[:80]}')
    print(f'  Count: {cnt}, IDs: {", ".join(ids)}')
    for r in rows:
        print(f'    ID={r[0]}: title="{r[1][:50]}", source={r[2]}, cat={r[3]}')

print()
print('=== DUPLICATE TITLES ===')
cur.execute('SELECT LOWER(TRIM(title)), COUNT(*) as cnt FROM opportunities GROUP BY LOWER(TRIM(title)) HAVING cnt > 1 ORDER BY cnt DESC LIMIT 30')
for title_lower, cnt in cur.fetchall():
    cur.execute('SELECT id, title, source, url FROM opportunities WHERE LOWER(TRIM(title)) = ?', (title_lower,))
    rows = cur.fetchall()
    ids = [str(r[0]) for r in rows]
    print(f'  Title: {rows[0][1][:60]} (x{cnt}, IDs: {", ".join(ids)})')

print()
print('=== MALFORMED URL CHECK ===')
cur.execute('SELECT id, url, source, title FROM opportunities ORDER BY id')
all_opps = cur.fetchall()
bad_urls = []
empty_urls = 0
for row in all_opps:
    oid, url, source, title = row
    if not url or url.strip() == '':
        empty_urls += 1
        bad_urls.append((oid, 'EMPTY', source, title))
    elif not url.startswith('http://') and not url.startswith('https://'):
        bad_urls.append((oid, url[:80], source, title))
print(f'Empty URLs: {empty_urls}')
print(f'Non-HTTP URLs: {len(bad_urls) - empty_urls}')
for row in bad_urls[:30]:
    print(f'  ID={row[0]}: url="{row[1][:80]}", source={row[2]}, title="{row[3][:50]}"')

print()
print('=== URLS BY SOURCE QUALITY ===')
cur.execute('SELECT source, COUNT(*) as total, SUM(CASE WHEN url IS NOT NULL AND url != \'\' AND (url LIKE \'http%\') THEN 1 ELSE 0 END) as valid FROM opportunities GROUP BY source')
for row in cur.fetchall():
    pct = row[2] / row[1] * 100 if row[1] > 0 else 0
    print(f'  {row[0]:20s}: {row[1]:4d} total, {row[2]:4d} valid ({pct:.0f}%)')

print()
print('=== CATEGORY MISMATCH (google_search items about grants) ===')
cur.execute("SELECT id, title, url, source, category FROM opportunities WHERE source = 'google_search' AND (LOWER(title) LIKE '%grant%' OR LOWER(title) LIKE '%funding%' OR LOWER(title) LIKE '%fellowship%') LIMIT 20")
for row in cur.fetchall():
    print(f'  ID={row[0]}: cat={row[4]}, title="{row[1][:60]}"')

conn.close()
