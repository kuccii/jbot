# job-hunter

A clean, focused job-hunt tool for **Rwanda-eligible roles** — jobs only. No
startups, no grants. It pulls from job boards that actually hire from Rwanda,
filters each listing for Rwanda eligibility, and stores the results in SQLite.

## Quick start

```bash
cd job-hunter

# 1. Edit config.yaml — set your profile (name, email, location, skills)

# 2. Fetch jobs from all enabled boards
python -m job_hunter discover

# 3. Browse the Rwanda-eligible jobs
python -m job_hunter list

# Track what you're doing with them
python -m job_hunter mark 12 applied
python -m job_hunter mark 7 hidden
python -m job_hunter purge hidden      # delete hidden ones
python -m job_hunter status            # counts per board
```

## Boards

| Board | Why it's in | Status |
|---|---|---|
| `remote4africa` | **Primary.** Uses the site's Rwanda feed (`/remote-jobs/rw`) and each posting's `applicantLocationRequirements` — the employer explicitly lists the countries it can hire from, Rwanda included | ✅ verified live |
| `remoteok` | Public JSON API; only worldwide-remote / empty-location postings pass (its feed now mixes in physical roles) | ✅ verified live |
| `weworkremotely` | Worldwide-remote listings with explicit region tags ("Anywhere in the World") | ⚠️ implemented; currently 403 to datacenter IPs, fails gracefully |

Enable/disable any board in `config.yaml`.

## How eligibility works

A job is kept only if it can realistically be done from Rwanda:

1. **Explicit country/region list** (Remote4Africa) → eligible iff `Rwanda` is
   listed, or a broader region that includes Rwanda ("Africa", "East Africa",
   "EMEA", "Worldwide", ...).
2. **Location text** (RemoteOK / WeWorkRemotely) → eligible when the region is
   worldwide-remote ("Anywhere", "🌏", "Worldwide", "100% Remote") or mentions
   Africa / East Africa / Rwanda. Rejected when it's a bare city (likely
   onsite), "USA only", "Europe", "UK only", "hybrid", etc.

`keywords` in `config.yaml` is an *optional* relevance filter: if non-empty, a
job must match at least one keyword (word-boundary) in its title/tags. It's
empty by default — every Rwanda-eligible job is kept and you curate with
`mark ... hidden`.

## Not included (yet)

- **RemoteAfrica.io** — client-rendered site; needs a headless browser.
- **Fuzu, Tunga** — reachable only from some networks / JS-heavy.

## Tests

```bash
cd job-hunter
python -m pytest tests -q
```
