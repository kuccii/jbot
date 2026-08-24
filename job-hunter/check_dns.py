#!/usr/bin/env python3
"""Check DNS error and 404 URLs."""
import sys, io, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DNS_ERRORS = [
    ("LiveWorld", "https://www.liveworldtext.com"),
    ("LiveWorld Workable", "https://apply.workable.com/liveworldtext/"),
    ("TTEC Careers", "https://careers.ttec.com"),
    ("TP Jobs", "https://jobs.teleperformance.com"),
    ("Foundever Careers", "https://careers.foundever.com"),
    ("Concentrix Careers", "https://careers.concentrix.com"),
    ("RedButterfly", "https://redbuterfly.com"),
    ("RedButterfly VA", "https://redbuterfly.com/become-a-virtual-assistant/"),
    ("Clickworker AI", "https://afia.clickworker.com"),
    ("Teemwork", "https://teemwork.ai"),
    ("Scale App", "https://app.scale.com"),
]

URLS_404 = [
    ("BELAY Careers", "https://www.belay.com/careers"),
    ("Appen AI", "https://appen.com/ai-community"),
    ("Arise CSP", "https://www.arise.com/csp"),
    ("Besedo Careers", "https://www.besedo.com/careers"),
    ("Scribie Freelance", "https://www.scribie.com/freelance-transcriptionist"),
    ("CastingWords Shop", "https://castingwords.com/shop/transcription"),
    ("ScribeMedia Writers", "https://scribemedia.com/writers"),
    ("PPH Signup", "https://www.peopleperhour.com/freelancer/signup"),
    ("Freelancer Register", "https://www.freelancer.com/register"),
    ("Guru Register", "https://www.guru.com/register"),
    ("Boldly Careers", "https://www.boldly.com/careers"),
    ("Gengo Signup", "https://gengo.com/translators/signup/"),
    ("1-Hour Apply", "https://www.onehourtranslation.com/translators/apply"),
    ("WriterAccess Sig", "https://www.writeraccess.com/signup"),
    ("CC Write", "https://www.constant-content.com/write-content"),
]

print("DNS RESOLUTION ERRORS:")
print(f"{'─'*80}")
for name, url in DNS_ERRORS:
    from urllib.parse import urlparse
    host = urlparse(url).hostname
    try:
        ip = socket.gethostbyname(host)
        print(f"  RESOLVES   {name[:25]:<27} {host} → {ip}")
    except Exception as e:
        print(f"  DEAD       {name[:25]:<27} {host} — {str(e)[:40]}")

print(f"\n{'─'*80}")
print("404 URL VERIFICATION (checking alternate paths):")
print(f"{'─'*80}")

from curl_cffi import requests as cffi_requests

checks = [
    ("BELAY Careers", [
        ("https://www.belay.com/careers", None),
        ("https://www.belay.com/jobs", None),
        ("https://www.belay.com/open-positions", None),
        ("https://jobs.lever.co/belay", None),
    ]),
    ("Appen AI", [
        ("https://appen.com/ai-community", None),
        ("https://appen.com/crowdsourcing", None),
        ("https://appen.com/work-with-us", None),
    ]),
    ("Arise CSP", [
        ("https://www.arise.com/csp", None),
        ("https://www.arise.com/opportunities", None),
        ("https://www.arise.com/find-opportunity", None),
    ]),
    ("Besedo Careers", [
        ("https://www.besedo.com/careers", None),
        ("https://www.besedo.com/jobs", None),
        ("https://www.besedo.com/join-our-team", None),
    ]),
    ("Scribie Freelance", [
        ("https://www.scribie.com/freelance-transcriptionist", None),
        ("https://www.scribie.com/freelancer", None),
        ("https://www.scribie.com/signup", None),
    ]),
    ("CastingWords Shop", [
        ("https://castingwords.com/shop/transcription", None),
        ("https://castingwords.com", None),
        ("https://castingwords.com/transcription-jobs", None),
    ]),
    ("PPH Signup", [
        ("https://www.peopleperhour.com/freelancer/signup", None),
        ("https://www.peopleperhour.com/signup", None),
        ("https://www.peopleperhour.com/register", None),
    ]),
    ("Freelancer Register", [
        ("https://www.freelancer.com/register", None),
        ("https://www.freelancer.com/signup", None),
        ("https://www.freelancer.com", None),
    ]),
    ("Guru Register", [
        ("https://www.guru.com/register", None),
        ("https://www.guru.com/signup", None),
        ("https://www.guru.com", None),
    ]),
    ("Boldly Careers", [
        ("https://www.boldly.com/careers", None),
        ("https://www.boldly.com/jobs", None),
        ("https://www.boldly.com/work-with-us", None),
    ]),
    ("Gengo Signup", [
        ("https://gengo.com/translators/signup/", None),
        ("https://gengo.com/signup", None),
        ("https://gengo.com", None),
    ]),
    ("WriterAccess", [
        ("https://www.writeraccess.com/signup", None),
        ("https://www.writeraccess.com/register", None),
        ("https://www.writeraccess.com", None),
    ]),
    ("CC Write", [
        ("https://www.constant-content.com/write-content", None),
        ("https://www.constant-content.com/writers", None),
        ("https://www.constant-content.com", None),
    ]),
    ("ScribeMedia Writers", [
        ("https://scribemedia.com/writers", None),
        ("https://scribemedia.com/apply", None),
        ("https://scribemedia.com", None),
    ]),
    ("Telus AI", [
        ("https://www.telusinternational.com/ai-community", None),
        ("https://www.telusdigital.com/ai-community", None),
        ("https://www.telusdigital.com/crowdsourcing", None),
    ]),
]

for name, urls in checks:
    found = False
    for url, _ in urls:
        try:
            r = cffi_requests.get(url, impersonate="safari", timeout=8, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 5000:
                final = str(r.url)
                print(f"  OK   {name[:25]:<27} → {final[:55]}")
                found = True
                break
            elif r.status_code == 404:
                continue
        except:
            continue
    if not found:
        print(f"  FAIL {name[:25]:<27} — all paths dead")
