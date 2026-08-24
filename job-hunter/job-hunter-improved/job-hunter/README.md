# job-hunter

Find jobs you can actually take from Rwanda or Kenya. `job-hunter` polls 15+
remote job boards and ATS APIs (Greenhouse, Ashby, SmartRecruiters),
throws out postings that are secretly location-restricted, scores what's
left against your own skills, and can ping you when something good shows up.

This is a cleaned-up, bug-fixed, and extended version of the `job-hunter`
package from this repo. What changed from the original:

**Fixed**
- `Store.search()` and `Store.get_job()` were called by `cli.py` but never
  existed in `models.py` — `job-hunter search` and `job-hunter details`
  crashed on every use. Both are now implemented and tested.
- `config.yaml` / `pyproject.toml` / `README.md` didn't exist in this
  folder, so the package couldn't be installed or configured on its own.

**Added**
- **Fit scoring** (`job_hunter/scoring.py`) — each eligible job gets a
  0–100 score based on how well it matches your `profile.skills` and
  `profile.seniority`, plus small boosts for salary transparency and
  freshness. `list`/`search`/the dashboard can sort by it.
- **Notifications** (`job_hunter/notifications.py`) — Telegram, a generic
  Slack/Discord webhook, and plain SMTP email. Each channel is optional and
  independent; a broken webhook never blocks the others or crashes a run.
- **`job-hunter watch`** — runs discovery on a loop for long-lived deploys
  (a VPS, a Docker container), as an alternative to a cron job.
- **`job-hunter notify-test`** — sends a fake job through every configured
  channel so you can verify setup before waiting for a real match.
- Dashboard: jobs can now be sorted by fit score, and the fit score (with
  its reasons) shows on the jobs list and detail page.
- A `config.example.yaml` documenting every option, with secrets pulled
  from environment variables (`${VAR_NAME}`) instead of committed in plain
  text.
- `pyproject.toml` with a `job-hunter` console entry point, so this folder
  installs and runs standalone (`pip install -e .`).
- Automatic schema migration — `score`, `score_reasons`, and `notified`
  columns are added to an existing `jobs.db` in place, so upgrading doesn't
  require deleting your database.

## Install

```bash
cd job-hunter
pip install -e .
cp config.example.yaml config.yaml
```

Edit `config.yaml`: set your `profile.skills`, the `keywords` you want jobs
to mention, and (optionally) `notifications`.

## Use

```bash
job-hunter discover          # fetch from all enabled boards, score, store, notify
job-hunter list               # eligible jobs, best fit first
job-hunter search "ai engineer"
job-hunter details 12
job-hunter mark 12 saved      # new / saved / applied / hidden
job-hunter status             # counts per board
job-hunter purge hidden       # delete hidden jobs
job-hunter dashboard          # web UI at http://127.0.0.1:8000
job-hunter watch --interval 3600   # discover on a loop instead of cron
job-hunter notify-test        # sanity-check your notification setup
```

Or without installing: `python -m job_hunter <command>` from this folder.

## How eligibility works

A job is stored only if it can realistically be done from Rwanda or Kenya.
See the docstring at the top of `job_hunter/eligibility.py` for the exact
rules — in short: explicit eligible-country lists win first, then location
text is checked after stripping "remote"-flavored words, then titles and
descriptions are scanned for hidden region/timezone restrictions and
generic non-postings (talent communities, campus programs, etc).

## How fit scoring works

Separate from eligibility. Each stored job gets 0–100 points from:
skill matches in the title (most weight), tags, or description (least
weight); a bonus for mentioning a salary; a bonus for being posted in the
last two days; and a bonus/penalty if the title's apparent seniority
matches/mismatches `profile.seniority`. See `job_hunter/scoring.py`.

## Notifications

All three channels in `config.yaml`'s `notifications` block are optional —
configure any subset. Set `notifications.enabled: true` and at least one
of `telegram_bot_token`+`telegram_chat_id`, `webhook_url`, or
`smtp_host`+`smtp_to`. `min_score` lets you only get pinged about jobs
above a fit threshold. Run `job-hunter notify-test` to check it's wired up
before relying on it.

## Boards

Toggle any board on/off under `boards:` in `config.yaml`. `ats` polls the
companies listed in `DEFAULT_ATS_COMPANIES` in `job_hunter/config.py`
(Greenhouse/Ashby/SmartRecruiters) — add or remove companies there.
`weworkremotely` defaults to off; it 403s from most datacenter IPs.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests use an in-memory/tmp-path SQLite database and mock all HTTP/SMTP
calls in the notification tests — no network access is needed to run the
suite. Board scrapers (`job_hunter/boards/`) are tested against saved
fixture responses in `tests/test_parsers.py`.
