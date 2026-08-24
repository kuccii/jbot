#!/usr/bin/env python3
"""Verify 403 URLs with curl_cffi Safari impersonation."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from curl_cffi import requests

# 403 URLs from httpx check
URLS_403 = [
    ("Fancy Hands", "https://www.fancyhands.com"),
    ("Fancy Hands Apply", "https://www.fancyhands.com/apply"),
    ("Telus Intl", "https://www.telusinternational.com"),
    ("Telus AI", "https://www.telusinternational.com/ai-community"),
    ("ModSquad", "https://www.modsquad.com"),
    ("ModSquad Careers", "https://join.modsquad.com/careers/"),
    ("TTEC", "https://www.ttec.com"),
    ("Alorica", "https://www.alorica.com"),
    ("Alorica Careers", "https://www.alorica.com/careers"),
    ("Crisp Thinking", "https://crispthinking.com"),
    ("Crisp Careers", "https://crispthinking.com/careers"),
    ("Fiverr", "https://www.fiverr.com"),
    ("Fiverr Sell", "https://www.fiverr.com/start_selling"),
    ("Upwork", "https://www.upwork.com"),
    ("Upwork Signup", "https://www.upwork.com/nx/signup/"),
    ("Toptal", "https://www.toptal.com"),
    ("Toptal Freelancers", "https://www.toptal.com/freelancers"),
    ("Remotasks", "https://www.remotasks.com"),
    ("Prolific", "https://www.prolific.co"),
    ("Outlier App", "https://app.outlier.ai"),
    ("Scale AI", "https://scale.com"),
    ("Alignerr", "https://www.alignerr.com"),
]

print("curl_cffi Safari impersonation results:")
print(f"{'─'*80}")
for name, url in URLS_403:
    try:
        r = requests.get(url, impersonate="safari", timeout=10, allow_redirects=True)
        final = str(r.url)
        content_len = len(r.text)
        has_jobs = "job" in r.text.lower()[:5000]
        status = f"[{r.status_code}]"
        redir = f" → {final[:50]}" if final.rstrip("/") != url.rstrip("/") else ""
        marker = "OK" if 200 <= r.status_code < 400 else "BLOCKED"
        print(f"  {status} {marker:8} {name[:25]:<27} ({content_len:>6} chars){redir}")
    except Exception as e:
        print(f"  [ERR]  FAIL    {name[:25]:<27} {str(e)[:50]}")

print(f"{'─'*80}")
