import re

path = "/root/job-hunter/job-hunter/job_hunter/dashboard/server.py"
s = open(path).read()

# 1. Add CORS import
s = s.replace(
    "from fastapi import FastAPI, Query, Request",
    "from fastapi import FastAPI, Query, Request\nfrom fastapi.middleware.cors import CORSMiddleware"
)

# 2. Add CORS middleware after app creation
s = s.replace(
    "app = FastAPI(title=\"Job Hunter Dashboard\", version=\"2.0.0\")",
    "app = FastAPI(title=\"Job Hunter Dashboard\", version=\"2.0.0\")\n\n# Allow cross-origin requests from the admin dashboard\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=[\"*\"],\n    allow_credentials=True,\n    allow_methods=[\"*\"],\n    allow_headers=[\"*\"],\n)"
)

# 3. Add cleanup API endpoint after the discover status endpoint
cleanup_endpoint = '''

@app.post("/api/cleanup")
def run_cleanup():
    """Run cleanup/reclassify on the database."""
    import subprocess, sys
    from job_hunter.config import load_config
    cfg = load_config()
    result = subprocess.run(
        [sys.executable, "-m", "job_hunter", "cleanup", "--reclassify"],
        capture_output=True, text=True, cwd="/app"
    )
    return JSONResponse({
        "status": "ok" if result.returncode == 0 else "error",
        "stdout": result.stdout,
        "stderr": result.stderr,
    })
'''

# Insert before the last function or at the end of file
# Find a good insertion point - after the stats endpoint
marker = '@app.get("/api/stats")'
idx = s.find(marker)
if idx != -1:
    # Find the end of the stats function
    next_func = s.find('\n@app.', idx + 1)
    if next_func != -1:
        s = s[:next_func] + cleanup_endpoint + s[next_func:]

open(path, 'w').write(s)
print("CORS and cleanup endpoint added")