import re
path = "/root/job-hunter/job-hunter/job_hunter/dashboard/server.py"
s = open(path).read()
lines = s.split('\n')
# Fix the broken lines (0-indexed: 310-314)
lines[310] = '    board: str = Query(""),'
lines[311] = '    status: str = Query(""),'
lines[312] = '    search: str = Query(""),'
lines[313] = '    audience: str = Query(""),'
lines[314] = '    sort: str = Query("entry_first"),'
s = '\n'.join(lines)
open(path, 'w').write(s)
print("done")