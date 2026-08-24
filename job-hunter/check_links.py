#!/usr/bin/env python3
"""Check all platform URLs for availability."""

import asyncio
import time

# All URLs from entry_platforms.py + gig_platforms.py + dashboard
URLS = [
    ("BELAY", "https://www.belay.com"),
    ("BELAY Careers", "https://www.belay.com/careers"),
    ("Time Etc", "https://www.timeetc.com"),
    ("Time Etc VA", "https://www.timeetc.com/for-virtual-assistants"),
    ("Zirtual", "https://www.zirtual.com"),
    ("Zirtual VA", "https://www.zirtual.com/virtual-assistants/"),
    ("Fancy Hands", "https://www.fancyhands.com"),
    ("Fancy Hands Apply", "https://www.fancyhands.com/apply"),
    ("Clickworker", "https://www.clickworker.com"),
    ("LXT", "https://lxt.ai"),
    ("MTurk", "https://www.mturk.com"),
    ("MTurk Worker", "https://www.mturk.com/worker"),
    ("Appen", "https://appen.com"),
    ("Appen AI", "https://appen.com/ai-community"),
    ("Telus Intl", "https://www.telusinternational.com"),
    ("Telus AI", "https://www.telusinternational.com/ai-community"),
    ("ModSquad", "https://www.modsquad.com"),
    ("ModSquad Careers", "https://join.modsquad.com/careers/"),
    ("Arise", "https://www.arise.com"),
    ("Arise CSP", "https://www.arise.com/csp"),
    ("LiveWorld", "https://www.liveworldtext.com"),
    ("LiveWorld Workable", "https://apply.workable.com/liveworldtext/"),
    ("TTEC", "https://www.ttec.com"),
    ("TTEC Careers", "https://careers.ttec.com"),
    ("Transcom", "https://www.transcom.com"),
    ("Transcom Careers", "https://www.transcom.com/careers"),
    ("Alorica", "https://www.alorica.com"),
    ("Alorica Careers", "https://www.alorica.com/careers"),
    ("Sutherland", "https://www.sutherlandglobal.com"),
    ("Sutherland Careers", "https://www.sutherlandglobal.com/careers"),
    ("Teleperformance", "https://www.teleperformance.com"),
    ("TP Jobs", "https://jobs.teleperformance.com"),
    ("Foundever", "https://www.foundever.com"),
    ("Foundever Careers", "https://careers.foundever.com"),
    ("Concentrix", "https://www.concentrix.com"),
    ("Concentrix Careers", "https://careers.concentrix.com"),
    ("TaskUs", "https://www.taskus.com"),
    ("TaskUs Careers", "https://www.taskus.com/careers"),
    ("OpenWeb", "https://www.openweb.com"),
    ("OpenWeb Careers", "https://www.openweb.com/careers"),
    ("Crisp Thinking", "https://crispthinking.com"),
    ("Crisp Careers", "https://crispthinking.com/careers"),
    ("Besedo", "https://www.besedo.com"),
    ("Besedo Careers", "https://www.besedo.com/careers"),
    ("Rev", "https://www.rev.com"),
    ("Rev Freelancers", "https://www.rev.com/freelancers"),
    ("TranscribeMe", "https://www.transcribeme.com"),
    ("GoTranscript", "https://www.gotranscript.com"),
    ("GoTranscript Jobs", "https://www.gotranscript.com/transcription-jobs"),
    ("Scribie", "https://www.scribie.com"),
    ("Scribie Freelance", "https://www.scribie.com/freelance-transcriptionist"),
    ("CastingWords", "https://castingwords.com"),
    ("CastingWords Shop", "https://castingwords.com/shop/transcription"),
    ("VerbalInk", "https://verbalink.com"),
    ("VerbalInk Apply", "https://verbalink.com/become-a-transcriptionist/"),
    ("ScribeMedia", "https://scribemedia.com"),
    ("ScribeMedia Writers", "https://scribemedia.com/writers"),
    ("Fiverr", "https://www.fiverr.com"),
    ("Fiverr Sell", "https://www.fiverr.com/start_selling"),
    ("Upwork", "https://www.upwork.com"),
    ("Upwork Signup", "https://www.upwork.com/nx/signup/"),
    ("PeoplePerHour", "https://www.peopleperhour.com"),
    ("PPH Signup", "https://www.peopleperhour.com/freelancer/signup"),
    ("Freelancer.com", "https://www.freelancer.com"),
    ("Freelancer Register", "https://www.freelancer.com/register"),
    ("Guru", "https://www.guru.com"),
    ("Guru Register", "https://www.guru.com/register"),
    ("Toptal", "https://www.toptal.com"),
    ("Toptal Freelancers", "https://www.toptal.com/freelancers"),
    ("Belay Solutions", "https://belaysolutions.com"),
    ("Belay Sol Careers", "https://belaysolutions.com/careers"),
    ("Boldly", "https://www.boldly.com"),
    ("Boldly Careers", "https://www.boldly.com/careers"),
    ("RedButterfly", "https://redbuterfly.com"),
    ("RedButterfly VA", "https://redbuterfly.com/become-a-virtual-assistant/"),
    ("Hive Micro", "https://www.hivemicro.com"),
    ("Remotasks", "https://www.remotasks.com"),
    ("Microworkers", "https://www.microworkers.com"),
    ("Picoworkers", "https://www.picoworkers.com"),
    ("Clickworker AI", "https://afia.clickworker.com"),
    ("Gengo", "https://gengo.com"),
    ("Gengo Signup", "https://gengo.com/translators/signup/"),
    ("1-Hour Trans", "https://www.onehourtranslation.com"),
    ("1-Hour Apply", "https://www.onehourtranslation.com/translators/apply"),
    ("Nuance", "https://www.nuance.com"),
    ("Nuance Careers", "https://www.nuance.com/company/careers.html"),
    ("Prolific", "https://www.prolific.co"),
    ("Prolific App", "https://app.prolific.co"),
    ("Toloka", "https://toloka.ai"),
    ("Toloka Web", "https://www.toloka.ai"),
    ("OneForma", "https://www.oneforma.com"),
    ("Teemwork", "https://teemwork.ai"),
    ("Textbroker", "https://www.textbroker.com"),
    ("Textbroker Reg", "https://www.textbroker.com/writers/register"),
    ("WriterAccess", "https://www.writeraccess.com"),
    ("WriterAccess Sig", "https://www.writeraccess.com/signup"),
    ("iWriter", "https://www.iwriter.com"),
    ("ConstantContent", "https://www.constant-content.com"),
    ("CC Write", "https://www.constant-content.com/write-content"),
    ("Outlier", "https://outlier.ai"),
    ("Outlier App", "https://app.outlier.ai"),
    ("Scale AI", "https://scale.com"),
    ("Scale App", "https://app.scale.com"),
    ("DataAnnotation", "https://www.dataannotation.tech"),
    ("Alignerr", "https://www.alignerr.com"),
    ("Surge AI", "https://www.surgehq.ai"),
]


async def check(name, url, client):
    result = {"name": name, "url": url, "status": 0, "redirect": "", "ok": False, "error": ""}
    try:
        r = await client.head(url, follow_redirects=True, timeout=12)
        result["status"] = r.status_code
        result["ok"] = 200 <= r.status_code < 400
        final = str(r.url)
        if final.rstrip("/") != url.rstrip("/"):
            result["redirect"] = final
    except Exception as e:
        err = str(e)[:80]
        result["error"] = err
        if "ssl" in err.lower():
            result["status"] = "SSL_ERR"
        elif "timeout" in err.lower():
            result["status"] = "TIMEOUT"
        elif "connect" in err.lower():
            result["status"] = "CONN_ERR"
        else:
            result["status"] = "ERROR"
    return result


async def main():
    import httpx
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    start = time.time()
    results = []

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=12,

        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    ) as client:
        for i in range(0, len(URLS), 15):
            batch = URLS[i:i+15]
            tasks = [check(name, url, client) for name, url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, Exception):
                    results.append({"name": "?", "url": "?", "status": "EXC", "ok": False, "error": str(r)[:60], "redirect": ""})
                else:
                    results.append(r)

    elapsed = time.time() - start
    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]

    print(f"\n{'='*90}")
    print(f"  LINK VERIFICATION REPORT — {len(results)} URLs checked in {elapsed:.1f}s")
    print(f"{'='*90}")
    print(f"  ✅ Working:  {len(ok)}")
    print(f"  ❌ Broken:   {len(fail)}")
    print(f"  📊 Success:  {len(ok)/len(results)*100:.0f}%")

    if fail:
        print(f"\n{'─'*90}")
        print(f"  ❌ BROKEN/DEAD LINKS ({len(fail)}):")
        print(f"{'─'*90}")
        for r in fail:
            status = r.get("status", "?")
            err = r.get("error", "")
            print(f"  [{status}] {r['name'][:30]:<32} {r['url'][:50]}")
            if err:
                print(f"  {'':38} Error: {err[:50]}")

    redirects = [r for r in ok if r["redirect"]]
    if redirects:
        print(f"\n{'─'*90}")
        print(f"  🔀 REDIRECTS ({len(redirects)}):")
        print(f"{'─'*90}")
        for r in redirects:
            print(f"  {r['name'][:30]:<32} {r['url'][:45]}")
            print(f"  {'':32} → {r['redirect'][:55]}")

    print(f"\n{'─'*90}")
    print(f"  ✅ WORKING LINKS ({len(ok)}):")
    print(f"{'─'*90}")
    for r in ok:
        redir = " ↪" if r["redirect"] else ""
        print(f"  [{r['status']}] {r['name'][:30]:<32} {redir}")

    print(f"\n{'='*90}")


if __name__ == "__main__":
    asyncio.run(main())
