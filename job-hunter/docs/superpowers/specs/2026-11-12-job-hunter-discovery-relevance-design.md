# Job Hunter — Discovery Relevance Design

**Date:** 2026-11-12
**Status:** Approved (design), pending implementation plan
**Scope:** `job-hunter` discovery pipeline — relevance and noise reduction only

---

## 1. Problem

Job Hunter's discovery pipeline stores mostly-irrelevant jobs. The live database
(`/app/data/jobs.db` on the VPS) holds **374 jobs, all `status='new'`**, with a
degenerate score distribution (**347 at 0**, 19 at 10, 5 at 20, 3 at 30), audience
tags `tech 192 / visa 83 / entry 39 / gig 10 / blank 50`, empty `company` on many
rows, and wrong-country listings such as *"Remote Recruiter – Ciudad de México, CDMX"*.

### Root cause (evidence-backed)

1. **The container runs the placeholder config.**
   `Dockerfile` contains `COPY config.example.yaml config.yaml`, so the image always
   bakes the *example* config. Confirmed: `md5(/app/config.yaml) == md5(config.example.yaml)`.
   The running profile is therefore `name: "Your Name"`, skills
   `python, django, postgresql, react`, `seniority: mid`, keywords
   `python|backend|fullstack`, **and every board enabled**.

2. **No real config ever reaches the container.**
   `docker-compose.yml` mounts only `./data:/app/data`; there is no config mount and
   no profile env. The repo root is `JBot/` (remote `kuccii/jbot`) with `job-hunter/`
   as a subdirectory, and the **root `.gitignore` line 14 ignores `config.yaml`
   anywhere in the tree** — so a clone never contains one, and the compose directory
   on the VPS (`/root/job-hunter/job-hunter/`) has only `config.example.yaml`.

3. **Eligibility is global; audience is only a post-hoc tag.**
   `check_eligibility()` runs one rule-set for everyone; `audience` is stamped
   afterward from a board→audience map (`orchestrator._BOARD_AUDIENCE`), leaving
   blank rows. There is no per-audience bar today.

4. **Scoring is CV-skill-overlap only.** `scoring.score_job()` rewards matches between
   configured skills and title/tags/description. Under the placeholder profile almost
   nothing matched → score 0 by construction. Even with a real profile this model is
   wrong for entry work, which legitimately matches no technical skill.

5. **Location heuristics leak.** A board that reports `location: "Remote"` is treated
   as "no location restriction", and title region detection matches region *codes*
   (AMER/APAC) but not city names (e.g. "Ciudad de México").

---

## 2. Goal and non-goals

**Goal.** Cut noise and fix relevance so stored jobs are genuinely actionable, across
three cleanly separated audiences.

**Non-goals.** Expanding source coverage; full loop automation (scheduling, digests,
nginx vhost); any change to `career-ops` beyond reading it as a profile source.

---

## 3. Requirements (locked)

- **Audiences:** `tech`, `entry` (entry/gig/online work), `visa`
  (visa-sponsorship/relocation) — each with its own eligibility bar, scoring, and
  dashboard view.
- **Noise to drop (all six):** wrong-country "remote"; off-profile titles; wrong
  seniority + generic postings; scam/bait/poverty-wage gigs; dead links + reposts +
  duplicates; unactionable rows missing company/description.
- **Aggressiveness:** Broad — hard rules drop clear noise, ranking sorts the rest.
- **Real profile:** Patrick Hirwa, impatrickhi@gmail.com, Rwanda, remote preferred;
  target roles Product Manager, AI/Automation Specialist, Software Engineer, Project
  Manager; skills from `cv.md` (Cloud Systems, AI & Automation, Mobile & Web
  Development, Databases, DevOps Tools, plus PM/ops skills).

---

## 4. Design

### 4.1 Config delivery and profile source of truth

**Delivery (Decision 1a → Option 1).** Add a **tracked** `job-hunter/config.production.yaml`
(respecting the "`config.yaml` is personal/ignored" convention) and mount it read-only in
`docker-compose.yml`:

```yaml
volumes:
  - ./data:/app/data
  - ./config.production.yaml:/app/config.yaml:ro
```

Keep the Dockerfile baking `config.example.yaml` as the fallback, so a checkout without
the production file still boots. Because the file is tracked, it always exists after
`git pull` — avoiding the dir/file conflict that commit `e4162f6` hit when it mounted a
missing file. Config edits then require `git pull` + `docker compose up -d` (no rebuild).

**Profile source of truth (Decision 1b → Option A).** `career-ops/config/profile.yml` +
`career-ops/cv.md` are human-authoritative. A local script `scripts/sync_profile.py`
reads them and rewrites the `profile:` block of `config.production.yaml`; the output is
committed. Generation happens locally before deploy (the VPS clone has no `career-ops`);
no runtime coupling.

```yaml
profile:
  name: Patrick Hirwa
  email: impatrickhi@gmail.com
  location: Rwanda
  seniority: mid          # keep mid + senior for tech
  skills: [ ...derived from cv.md... ]
```

### 4.2 Audience model and routing

Three canonical audiences: **`tech`**, **`entry`**, **`visa`**. Existing `gig` and
`creative` values fold into `entry`; blanks are derived on re-eval.

Audience is **decided by routing, not stamped by boards**. For each candidate job,
evaluate audience rule-sets in priority order; the first whose gates all pass wins;
none means the job is dropped:

1. **`visa`** — board is `visa_sponsorship` **and** an explicit sponsorship signal
   **and** a real role title.
2. **`tech`** — title/description matches a target tech family **and** passes the tech
   location gate.
3. **`entry`** — title matches an entry/online family **and** passes the entry location gate.

Board origin is only a *hint* that sets the starting point (visa board starts at `visa`;
gig/entry boards start at `entry`), never the final decision. The same title is judged
per-audience: "Remote Administrative Assistant" is kept for `entry` and dropped for
`tech`; "Recruiter" is dropped for `tech` but may survive `entry` if real and
Rwanda-workable. `entry` stays a single flat list; gig/AI-training platforms remain
distinguishable through the existing `board` field.

### 4.3 Per-audience hard gates

A job must pass **every** gate of the audience it routes into. All lists live in
`config.production.yaml` under an `audiences:` block.

| Gate (noise category) | `tech` | `entry` | `visa` |
|---|---|---|---|
| **Country / workability** (#1) | Rwanda-workable (fixed location heuristics) | same | sponsorship check replaces location |
| **Title** (#2) | allow tech families (eng, dev, product, project, AI/automation, data, DevOps, QA); deny recruiter, tutor, admin, support, sales, nurse, marketing, accounting | allow entry families (VA, admin, support, tutor, data entry, annotation, transcription, moderation, content, bookkeeping, IT/chat support); deny clinical/physical roles | allow target families; deny generic/agency spam |
| **Seniority + generic** (#3) | drop principal/staff/distinguished/director/VP/head/chief; drop talent-community / general-application / campus / student | drop senior/lead/manager/director; drop the same generic set | drop director+; drop the same generic set |
| **Scam / bait / poverty-wage** (#4) | extend `scam_filter`: unpaid, commission-only, MLM, pay-to-work, "training fee" | same **plus** the wage floor (below) | same |
| **Metadata minimum** (#6) | require company **and** a real description | require URL **and** (company **or** a real description) | require URL **and** description |

**Metadata threshold:** "a real description" means **≥ 40 characters of non-boilerplate
text** (boilerplate = the board's own stub, e.g. "found via web search"). Below that, the
description counts as missing.

**Wage floor (concrete):** a configurable `wage_floor_usd_per_hour` (default **4.0**).
Drop a posting when a *detected* hourly rate is below the floor, or when the rate is
per-task **and** clearly below the floor after conversion. Always drop explicit
`unpaid` / `commission-only` / MLM / pay-to-work / "training fee" postings. When no rate
is detectable, do not drop on wage grounds (rank low instead).

**Country gate (the crux of #1).** Reuse and fix `eligibility.check_eligibility()`:
(a) a board-reported bare `"Remote"` must not be treated as "no restriction" when the
title/description names a place; (b) title region detection extends from region *codes*
to city names.

**Wage floor is conservative** so legitimate per-task gig work (Outlier/Alignerr-style)
survives; only clear poverty-wage, unpaid, or commission-only postings are dropped.

**Metadata differs by audience** because search boards (`indeed_search`) structurally
cannot supply a company; the `entry` bar tolerates that, the `tech` bar requires it.

### 4.4 Scoring — three audience rankers

One ranker per audience, all normalised 0–100 so sorting within a view works. Every
score carries human-readable `score_reasons`.

- **`tech`** — role-family match in the title (largest weight) + real CV-skill overlap
  + seniority fit + recency + salary mention.
- **`entry`** — deliberately **not** CV-skill-driven: platform tier (known-good platforms
  ranked higher), pay signal, recency, inverse scam-risk.
- **`visa`** — role-family fit + CV-skill overlap + sponsorship explicitness + company
  identifiable + recency.

Role-family lists (shared with the §4.3 title gate) live in config; weight constants stay
in Python.

**Structural change:** the global `keywords` gate (`matches_keywords()`) is **retired**.
The per-audience title allow-lists become the relevance filter. `keywords` remains in the
schema but defaults to empty and is ignored — one filter, not two.

### 4.5 Pipeline wiring

New module **`job_hunter/relevance.py`**: route a job to its audience and apply that
audience's gates. It calls existing pieces (`eligibility.check_eligibility`,
`scam_filter.is_unreliable`) and the new per-audience config rules.
`orchestrator._run_board` becomes: fetch → `relevance.route_and_gate(job)` → score with
the audience ranker → store.

```
board.fetch()
 └─ for each job:
      1. scam filter (extended)
      2. route to audience (visa → tech → entry); none = dropped
         gates: country · title · seniority+generic · metadata
      3. score with that audience's ranker → audience, score, reasons
      4. store
 — after all boards —
 5. cross-board dedupe (normalized title+company)
 6. repost detection (seen before → bump seen_count, flag repost)
 7. link liveness — HEAD (GET fallback), NEW rows only, short timeout;
    dead/404/410 → eligible=0 + note
```

**Placement decisions:** liveness runs post-discovery (not inline) to avoid slowing every
board, and only on new rows. Dead links are soft-marked (`eligible=0` + note), not silently
deleted, so they stay auditable and `cleanup.py` can purge later.

### 4.6 Re-evaluating the existing 374 rows

Extend `cleanup.py` with an idempotent `--reclassify` mode: re-derive audience, re-apply
gates, re-score, dedupe + repost-detect, then a one-time link-liveness pass.

**History protection:** pruning applies to **`status='new'` rows only**. Rows already
`applied`/`hidden`/`skipped` are re-audienced and re-scored but **never deleted**.

**Expectation:** the row count drops substantially — that is the point. "Broad" means keep
everything that passes the *fixed* rules; most current rows were admitted under the
placeholder config.

Runs once on the VPS after deploy, then available as
`python -m job_hunter cleanup --reclassify`.

### 4.7 Dashboard

- Audience filter collapses to **Tech / Entry / Visa** in `jobs.html`; `home.html` bars
  and `platforms.html` tabs follow (drop `creative`/`gig`).
- Surface previously invisible data: `score_reasons`, repost flag / `seen_count`, link
  status, `posted_at`/`found_at`.
- `detail.html` shows audience, score reasons, repost state.

---

## 5. Data model changes (small, additive)

- Constrain `audience` to `tech | entry | visa`; migrate existing `gig`/`creative` → `entry`;
  blanks derived on re-eval.
- Add `seen_count` (integer, default 1) and `last_seen_at` for repost detection.
- `score_reasons` already exists and is reused for the "why ranked" display.

---

## 6. Testing (pytest)

- **Routing:** per-audience fixtures — wrong-country recruiter, real tech role, entry VA,
  visa posting, scam, metadata-thin row — assert correct audience or drop.
- **Gates:** positive + negative case for each of the six noise categories, including the
  `Remote`-but-named-city leak.
- **Scoring:** entry jobs are no longer 0-by-construction; tech/visa rank sensibly.
- **Dedupe/repost:** `seen_count` increments; reposts flagged, not duplicated.
- **Migration:** `gig`/`creative` → `entry`; blanks derived.
- **Integration:** run the router over a small fixture DB.

---

## 7. Deploy

1. Local: `scripts/sync_profile.py` → commit `config.production.yaml`.
2. Push → VPS `cd /root/job-hunter && git pull`.
3. `cd job-hunter && docker compose up -d --build`.
4. Run `cleanup --reclassify` once.
5. Verify the dashboard: three populated views, non-degenerate scores, real profile.

---

## 8. Acceptance criteria

- The six noise categories are demonstrably dropped.
- Three dashboard views populate (`tech`, `entry`, `visa`).
- The placeholder profile is gone from the running container.
- The score distribution is no longer degenerate (entry jobs score > 0 by construction).
- Existing `applied`/`hidden`/`skipped` rows are preserved.

**Phasing (for the implementation plan):** the work is one coherent change but should land
in independently deployable phases — (1) config delivery + profile sync, (2) relevance
module + per-audience gates + scoring, (3) pipeline wiring + `cleanup --reclassify`,
(4) dashboard + tests. Phase 1 alone already fixes the placeholder-profile root cause.

---

## 9. Out of scope

- New/expanded boards or source coverage.
- Scheduled discovery, digest notifications, dashboard nginx vhost.
- Any modification to the `career-ops` project (read-only profile source).

---

## 10. Decisions log

| # | Decision | Choice |
|---|---|---|
| 1a | Config delivery | Tracked `config.production.yaml`, read-only mounted; example baked as fallback |
| 1b | Profile source of truth | Local `scripts/sync_profile.py` from `career-ops`; committed output |
| 2 | Audiences | Three canonical: `tech`, `entry`, `visa`; `gig`/`creative` → `entry` |
| 2b | Routing | Priority visa → tech → entry; first pass wins; none = dropped |
| 2c | Entry sub-label | None (flat `entry`; `board` field distinguishes gig platforms) |
| 3 | Tech seniority | Keep mid + senior; drop principal/staff/director+ |
| 3b | Wage floor | Conservative; legitimate per-task gig work survives |
| 4 | Scoring | Per-audience rankers; entry not CV-skill-driven |
| 4b | Keyword gate | Retired; per-audience title allow-lists are the filter |
| 5 | Liveness | Post-discovery, new rows only; soft-mark `eligible=0` |
| 6 | Re-eval pruning | `status='new'` only; history preserved |
