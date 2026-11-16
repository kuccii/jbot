import re
path = "/root/job-hunter/job-hunter/job_hunter/dashboard/server.py"
s = open(path).read()
s = s.replace('help="Filter by board", ', '')
s = s.replace('help="Filter by status", ', '')
s = s.replace('help="Search keywords", ', '')
s = s.replace('help="Filter by audience", ', '')
s = s.replace('help="entry_first, found_at, or score", ', '')
open(path, "w").write(s)
print("done")