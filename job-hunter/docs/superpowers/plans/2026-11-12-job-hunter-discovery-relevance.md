# Job Hunter — Discovery Relevance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `job-hunter` from storing irrelevant jobs by (a) delivering the real profile to the container and (b) replacing the global eligibility/keyword filter with three audience-specific rule-sets (`tech`, `entry`, `visa`) plus per-audience ranking.

**Architecture:** Four independently deployable phases.
1. **Config delivery** — a *tracked* `config.production.yaml` mounted read-only, its `profile:` block generated from `career-ops` by a local script. This alone kills the placeholder-profile root cause.
2. **Relevance module** — new `job_hunter/relevance.py` routes each job to the first audience whose gates all pass (`visa → tech → entry`; none = dropped); `scoring.py` gains one ranker per audience.
3. **Pipeline wiring** — `orchestrator`/dashboard call the router; `models.py` gains repost counters; a post-discovery link-liveness pass soft-marks dead rows; `cleanup --reclassify` re-evaluates the existing database.
4. **Dashboard + docs** — collapse to three audience views and surface score reasons, repost count, link status.

**Tech Stack:** Python 3.11+, pydantic v2, PyYAML, httpx, FastAPI + Jinja2, SQLite (stdlib), pytest + pytest-asyncio (`asyncio_mode = "auto"`).

**Spec:** `job-hunter/docs/superpowers/specs/2026-11-12-job-hunter-discovery-relevance-design.md` (approved; commit `502f557`).

**Branch:** `feat/opportunity-categories` (1 commit ahead of `origin`, **not pushed**). Git root is `JBot/`; `job-hunter/` is a subdirectory. **Run every command from `job-hunter/`.**

**Tests:** `python -m pytest -q` (from `job-hunter/`). All work is TDD: write the failing test first, then the code.

---

## Global Constraints

- **Audiences are exactly** `tech`, `entry`, `visa`. `gig`/`creative` are legacy input values only — they are normalized to `entry` at every boundary. After this work, no row and no UI shows `gig` or `creative`.
- **Routing priority is fixed:** `visa → tech → entry`. First rule-set whose gates all pass wins. None pass ⇒ job is dropped (not stored).
- **Board origin is a hint, never the decision.** The board→audience maps in `orchestrator.py` and `dashboard/server.py` are deleted; only `relevance.route()` decides.
- **Broad aggressiveness:** hard gates drop *clear* noise; ranking sorts the rest. Do not add gates beyond those in the spec table.
- **Retire `matches_keywords()`.** Per-audience title allow-lists are the only relevance filter. `keywords` stays in the config schema, defaults to empty, and is ignored.
- **Pruning safety:** re-evaluation may delete only rows with `status='new'`. `applied`/`hidden`/`skipped` rows are re-audienced and re-scored but **never** deleted.
- **No changes to the `career-ops` project** — it is a read-only profile source.
- **Config lists live in code, are overridable from `config.production.yaml`.** Single source of truth is `job_hunter/audience_rules.py`; `config.production.yaml` pins the same values and a test asserts they agree (no drift).
- Commit after every task with a conventional message. Do not push until Phase 1 is verified end-to-end.

## Review Focus

The spec is a vision document; these are the input classes it implies but does
not spell out. Each one gets a test in the task that owns the code (named
below), because each is a way a real posting breaks the router.

1. **A title that matches both an entry family and a tech family** (e.g.
   "Technical Support Engineer" — "technical support" is entry, "engineer" is
   tech). Priority `visa → tech → entry` must decide; a user expects it under
   **tech**, not entry. *(Task 2.3)*
2. **A salary stated as an annual figure** ("Compensation: $120,000 per year").
   The wage parser must not read it as an hourly rate and drop the posting.
   *(Task 2.3)*
3. **A `visa_sponsorship` posting that also names a restricted country**
   ("Remote (US only)"). The sponsorship gate replaces the location gate, so
   it must still route to **visa**. *(Task 2.3)*
4. **A row with an empty or non-`http` URL** reaching `classify`. It must be
   dropped cleanly, never raise. *(Task 2.3)*
5. **A legacy `gig`/`creative` or blank-audience row that is already history**
   (`applied`/`hidden`/`skipped`). Reclassify must never delete it, and it must
   never surface under a canonical view with a retired audience value.
   *(Task 3.4)*

## File Map

**New files**
- `job-hunter/job_hunter/profile_sync.py` — pure logic: derive profile from `career-ops`, render/replace the `profile:` block.
- `job-hunter/scripts/sync_profile.py` — thin CLI wrapper around `profile_sync`.
- `job-hunter/job_hunter/audience_rules.py` — canonical gate lists (title allow/deny, seniority, generic, boilerplate, wage floor).
- `job-hunter/job_hunter/relevance.py` — routing + gates + `classify()`.
- `job-hunter/job_hunter/liveness.py` — reusable URL-liveness check (extracted from `validate_links.py`).
- `job-hunter/config.production.yaml` — the tracked runtime config (mounted read-only).
- `job-hunter/tests/test_profile_sync.py`, `test_audience_rules.py`, `test_relevance.py`, `test_liveness.py`, `test_reclassify.py`.

**Modified files**
- `job-hunter/docker-compose.yml` — add the read-only config mount.
- `job-hunter/job_hunter/config.py` — `AudiencesConfig` + `wage_floor_usd_per_hour`.
- `job-hunter/job_hunter/eligibility.py` — city-name leak fix; delete `matches_keywords`.
- `job-hunter/job_hunter/boards/scam_filter.py` — poverty-wage / pay-to-work patterns.
- `job-hunter/job_hunter/scoring.py` — per-audience rankers (legacy behavior preserved for `score_job` defaults).
- `job-hunter/job_hunter/models.py` — `seen_count`, `last_seen_at`, `repost`, `link_status`, `link_checked_at`.
- `job-hunter/job_hunter/orchestrator.py` — rewire to `relevance.classify`; post-discovery liveness.
- `job-hunter/job_hunter/cleanup.py` — `reclassify()`.
- `job-hunter/job_hunter/cli.py` — `cleanup --reclassify`.
- `job-hunter/job_hunter/validate_links.py` — import the shared checker.
- `job-hunter/job_hunter/dashboard/server.py` + `templates/{jobs,home,platforms,detail}.html`.
- `job-hunter/tests/test_eligibility.py` — drop `matches_keywords` assertions.
- `job-hunter/README.md` — document production config + reclassify.

**Deleted / retired**
- `orchestrator._BOARD_AUDIENCE`, `dashboard/server.py` `_BOARD_AUDIENCE` + inline routing.
- `eligibility.matches_keywords()` and its three tests.

## Phase Overview

| Phase | Deliverable | Independently deployable? |
|---|---|---|
| 1 | Real profile reaches the container | Yes — fixes the root cause alone |
| 2 | Relevance module + gates + rankers | Yes — unit-tested, not yet wired |
| 3 | Pipeline + cleanup reclassify | Yes — needs 1 + 2 |
| 4 | Dashboard + docs | Yes — needs 3 |

---
# Phase 1 — Config delivery & profile source of truth

**Outcome:** the running container reads a real profile, and the profile can be regenerated from `career-ops` with one command. Deployable on its own.

## Task 1.1 — `job_hunter/profile_sync.py` (pure logic)

**Files:** create `job_hunter/profile_sync.py`; create `tests/test_profile_sync.py`.

The module must not depend on `career-ops` at import time — it takes text in and returns data. This keeps it unit-testable and VPS-safe.

- [ ] **Step 1: Write the failing tests.** Cover four behaviors:

```python
# tests/test_profile_sync.py
from job_hunter import profile_sync

CV = """
## Skills
### Technical Expertise
Cloud Systems, AI & Automation, Mobile & Web Development, Databases, DevOps Tools
### Project & Product Management
Product Planning & Roadmapping, KPI Tracking & Performance Analysis, Agile & Scrum Methodologies
"""

PROFILE_YML = {
    "name": "Patrick Hirwa",
    "email": "impatrickhi@gmail.com",
    "location": "Rwanda",
    "target_roles": ["Product Manager", "AI / Automation Specialist",
                     "Software Engineer", "Project Manager"],
}

def test_derive_skills_expands_cv_phrases_and_roles():
    skills = profile_sync.derive_skills(CV, PROFILE_YML["target_roles"])
    assert "product manager" in skills
    assert "automation" in skills          # from "AI & Automation"
    assert "docker" in skills              # from "DevOps Tools"
    assert "sql" in skills                 # from "Databases"
    assert skills == sorted(set(skills))   # deduped + stable order

def test_build_profile_shape():
    p = profile_sync.build_profile(PROFILE_YML, CV)
    assert p["name"] == "Patrick Hirwa"
    assert p["email"] == "impatrickhi@gmail.com"
    assert p["location"] == "Rwanda"
    assert p["seniority"] == "mid"
    assert isinstance(p["skills"], list) and p["skills"]

def test_replace_profile_block_is_surgical():
    cfg = "profile:\n  name: \"Your Name\"\n  skills:\n    - python\nboards:\n  remoteok: true\n"
    out = profile_sync.replace_profile_block(cfg, {"name": "Patrick Hirwa", "skills": ["ai"]})
    assert "Patrick Hirwa" in out
    assert "Your Name" not in out
    assert "boards:\n  remoteok: true" in out   # untouched

def test_replace_profile_block_handles_eof():
    cfg = "boards:\n  remoteok: true\nprofile:\n  name: x\n"
    out = profile_sync.replace_profile_block(cfg, {"name": "Y"})
    assert out.rstrip().endswith("name: Y")
```

- [ ] **Step 2: Run them, confirm they fail** (`python -m pytest tests/test_profile_sync.py -q`).

- [ ] **Step 3: Implement.** Public API:

```python
# job_hunter/profile_sync.py
from __future__ import annotations
import re
from pathlib import Path
import yaml

# The only hand-maintained bridge: CV skill phrases -> job-text tokens.
# Multi-word CV headings do not match job postings directly, so each expands
# to the tokens scoring actually looks for. Extend when cv.md gains a skill.
SKILL_EXPANSIONS: dict[str, list[str]] = {
    "cloud systems": ["cloud", "aws", "azure", "gcp"],
    "ai & automation": ["ai", "automation", "llm", "machine learning", "prompt"],
    "mobile & web development": ["mobile", "web", "react", "javascript", "python", "api"],
    "databases": ["sql", "postgresql", "database"],
    "devops tools": ["devops", "docker", "kubernetes", "ci/cd"],
    "product planning & roadmapping": ["product management", "product manager", "roadmap"],
    "task prioritization & resource allocation": ["prioritization", "resource planning"],
    "kpi tracking & performance analysis": ["kpi", "analytics", "metrics"],
    "agile & scrum methodologies": ["agile", "scrum"],
    "project management": ["project management", "project manager"],
}

_PROFILE_BLOCK_RE = re.compile(r"(?ms)^profile:.*?(?=^\S)")

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def derive_skills(cv_text: str, target_roles: list[str]) -> list[str]:
    """Expand CV skill phrases + target roles into scoring tokens."""
    tokens: set[str] = set()
    for line in cv_text.splitlines():
        for phrase in line.split(","):
            key = _norm(phrase)
            if key in SKILL_EXPANSIONS:
                tokens.update(SKILL_EXPANSIONS[key])
    for role in target_roles:
        tokens.add(_norm(role))
    return sorted(t for t in tokens if t)

def build_profile(profile_yml: dict, cv_text: str) -> dict:
    return {
        "name": profile_yml.get("name", ""),
        "email": profile_yml.get("email", ""),
        "location": profile_yml.get("location", "Rwanda"),
        "seniority": "mid",
        "skills": derive_skills(cv_text, profile_yml.get("target_roles", [])),
    }

def replace_profile_block(config_text: str, profile: dict) -> str:
    """Replace the top-level ``profile:`` block, preserving everything else."""
    body = yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)
    block = "profile:\n" + "".join("  " + ln + "\n" for ln in body.splitlines())
    if _PROFILE_BLOCK_RE.search(config_text):
        return _PROFILE_BLOCK_RE.sub(block, config_text, count=1)
    sep = "" if config_text.endswith("\n") else "\n"
    return config_text + sep + block
```

- [ ] **Step 4: Run the tests, confirm green.** Then commit: `feat(job-hunter): add profile_sync (career-ops -> config profile block)`.

## Task 1.2 — `scripts/sync_profile.py` (CLI wrapper)

**Files:** create `scripts/sync_profile.py`.

- [ ] **Step 1: Implement.**

```python
#!/usr/bin/env python3
"""Regenerate the ``profile:`` block of config.production.yaml from career-ops.

    python scripts/sync_profile.py                 # uses ../career-ops (sibling of the repo root)
    python scripts/sync_profile.py --career-ops /path/to/career-ops
    python scripts/sync_profile.py --check          # exit 1 if the file would change

Run from the ``job-hunter/`` directory. The VPS clone has no career-ops, so
this runs locally and the output is committed.
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_hunter import profile_sync  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]          # .../JBot
CONFIG = Path(__file__).resolve().parents[1] / "config.production.yaml"

def _default_career_ops() -> Path:
    env = os.environ.get("CAREER_OPS_DIR")
    if env:
        return Path(env)
    for cand in (REPO_ROOT.parent / "career-ops", REPO_ROOT / "career-ops"):
        if (cand / "config" / "profile.yml").exists():
            return cand
    return REPO_ROOT.parent / "career-ops"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--career-ops", default=str(_default_career_ops()))
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--check", action="store_true", help="exit 1 if a change is needed")
    args = ap.parse_args()

    co = Path(args.career_ops)
    profile_yml = yaml.safe_load((co / "config" / "profile.yml").read_text(encoding="utf-8"))
    cv_text = (co / "cv.md").read_text(encoding="utf-8")
    profile = profile_sync.build_profile(profile_yml, cv_text)

    cfg_path = Path(args.config)
    old = cfg_path.read_text(encoding="utf-8")
    new = profile_sync.replace_profile_block(old, profile)
    if args.check:
        if old != new:
            print("profile block is stale; run scripts/sync_profile.py", file=sys.stderr)
            return 1
        print("profile block up to date")
        return 0
    cfg_path.write_text(new, encoding="utf-8")
    print(f"wrote profile block to {cfg_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test against the real sibling project** (read-only):

```powershell
python scripts/sync_profile.py --career-ops ..\..\career-ops --config $env:TEMP\prod_test.yaml
```

If `config.production.yaml` does not exist yet, first create it in Task 1.3, then run `python scripts/sync_profile.py --check` and expect exit 1, then run without `--check` and expect exit 0.

- [ ] **Step 3: Commit:** `feat(job-hunter): add sync_profile CLI for config.production.yaml`.

## Task 1.3 — Track `config.production.yaml` + mount it

**Files:** create `config.production.yaml`; modify `docker-compose.yml`.

- [ ] **Step 1: Create `config.production.yaml`** as a copy of `config.example.yaml` (same top-level keys) with these changes:
  - leave the `profile:` block with placeholder values (Task 1.2 overwrites it — the committed copy must be the *generated* one);
  - **boards:** enable only the boards that feed the three audiences and disable the off-profile/unreliable ones. Use exactly:

```yaml
boards:
  remoteok: true
  remote4africa: true
  himalayas: true
  remotive: true
  jobicy: true
  workingnomads: true
  persona: true
  ats: true
  arc: true
  foundthejob: true
  dynamitejobs: true
  trulyremote: true
  startupjobs: true
  meetfrank: true
  workday: true
  entry_platforms: true
  indeed_entry: true
  wwr_entry: true
  indeed_search: true
  visa_sponsorship: true
  gig_platforms: true
  opentrain: true
  alignerr: true
  outlier: true
  indeed: false            # broad, low-reliability, wrong-country heavy
  weworkremotely: false    # 403s from datacenter IPs
```

  - **keywords:** `[]` (retired; see Global Constraints).
  - add the Phase-2 blocks now so the file is complete (values filled in Task 2.1/2.2):

```yaml
wage_floor_usd_per_hour: 4.0
audiences:
  tech:  {}
  entry: {}
  visa:  {}
```

- [ ] **Step 2: Generate the real profile** from the sibling `career-ops`:

```powershell
python scripts/sync_profile.py --career-ops ..\..\career-ops
```

  Confirm `profile.name` is `Patrick Hirwa`, `profile.email` is `impatrickhi@gmail.com`, and `profile.skills` is a non-empty list (not `python, django, postgresql, react`).

- [ ] **Step 3: Add the mount** to `docker-compose.yml` under `volumes:`:

```yaml
    volumes:
      - ./data:/app/data
      - ./config.production.yaml:/app/config.yaml:ro
```

  Leave the `Dockerfile` line `COPY config.example.yaml config.yaml` untouched — it is the fallback for a checkout without the production file.

- [ ] **Step 4: Verify no ignore rule blocks the file:**

```powershell
git -C .. check-ignore -v job-hunter/config.production.yaml   # expect: no output (not ignored)
git -C .. status --short
```

  If it were ignored, add `!job-hunter/config.production.yaml` after line 14 of the root `.gitignore`. Expect it *not* to be ignored.

- [ ] **Step 5: Commit:** `feat(job-hunter): track config.production.yaml and mount it read-only`.

## Task 1.4 — Verify the container runs the real profile

- [ ] **Step 1: Build + start locally** (or on the VPS) and prove the placeholder is gone:

```bash
docker compose up -d --build
docker exec job-hunter md5sum /app/config.yaml
docker exec job-hunter python -c "from job_hunter.config import load_config; c=load_config(); print(c.profile.name, c.profile.email, c.profile.skills[:5])"
```

  Acceptance: the printed name is `Patrick Hirwa`, and the md5 of `/app/config.yaml` differs from `config.example.yaml`.

- [ ] **Step 2: Deploy Phase 1 to the VPS** (this is a real, useful milestone on its own):

```bash
# local
git push origin feat/opportunity-categories
# VPS
cd /root/job-hunter && git pull
cd job-hunter && docker compose up -d --build
docker exec job-hunter python -c "from job_hunter.config import load_config; print(load_config().profile.name)"
```

- [ ] **Step 3:** Mark Phase 1 done in the tracker (`docs/superpowers/plans/job-hunter-discovery-relevance.md`).

---
# Phase 2 — Relevance module (gates + rankers)

**Outcome:** `job_hunter/relevance.py` can classify any `Job` into `tech`/`entry`/`visa` or drop it, with a score and reasons. Fully unit-tested and not yet wired into the pipeline (that is Phase 3), so it is safe to land.

## Task 2.1 — `job_hunter/audience_rules.py` (canonical gate lists)

**Files:** create `job_hunter/audience_rules.py`; create `tests/test_audience_rules.py`.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_audience_rules.py
from job_hunter import audience_rules as ar

def test_match_any_is_word_boundary():
    assert ar.match_any("Senior Python Engineer", ar.TECH_TITLE_ALLOW) == "engineer"
    # "ai" must not match inside "maintenance" / "email"
    assert ar.match_any("Maintenance Coordinator", ["ai"]) is None
    assert ar.match_any("Salesforce Developer", ar.TECH_TITLE_DENY) is None

def test_deny_lists_catch_off_profile_titles():
    for title in ["Technical Recruiter", "Online Tutor", "Customer Support Agent",
                  "Sales Manager", "Registered Nurse", "Marketing Manager",
                  "Data Entry Clerk"]:
        assert ar.match_any(title, ar.TECH_TITLE_DENY), title

def test_tech_allow_keeps_target_families():
    for title in ["Software Engineer", "Product Manager", "AI Automation Specialist",
                  "Project Manager", "DevOps Engineer", "Data Scientist"]:
        assert ar.match_any(title, ar.TECH_TITLE_ALLOW), title

def test_entry_allow_keeps_entry_families():
    for title in ["Virtual Assistant", "Data Annotator", "Transcriptionist",
                  "Content Moderator", "Customer Support Agent", "Online Tutor"]:
        assert ar.match_any(title, ar.ENTRY_TITLE_ALLOW), title

def test_lists_are_populated_and_lowercase():
    for name in ("TECH_TITLE_ALLOW", "TECH_TITLE_DENY", "ENTRY_TITLE_ALLOW",
                 "ENTRY_TITLE_DENY", "VISA_TITLE_DENY", "SENIORITY_DENY",
                 "GENERIC_DENY"):
        terms = getattr(ar, name)
        assert terms, name
        assert all(t == t.lower() for t in terms), name
```

- [ ] **Step 2: Run, confirm failure.**

- [ ] **Step 3: Implement.**

```python
# job_hunter/audience_rules.py
"""Canonical gate lists for the three audiences.

Single source of truth. ``config.production.yaml`` carries an ``audiences:``
block that can override any list; an empty block inherits these defaults, and
``tests/test_audience_config.py`` asserts the two never drift.
"""
from __future__ import annotations

import re
from functools import lru_cache

TECH_TITLE_ALLOW = [
    "engineer", "developer", "programmer", "software", "backend", "back-end",
    "frontend", "front-end", "full stack", "fullstack", "full-stack",
    "devops", "sre", "site reliability", "platform", "infrastructure",
    "cloud", "data engineer", "data scientist", "data analyst",
    "machine learning", "ml engineer", "ai engineer", "ai", "artificial intelligence",
    "automation", "product manager", "product owner", "product lead",
    "project manager", "project lead", "program manager", "technical program",
    "qa", "quality assurance", "test engineer", "security engineer",
    "mobile engineer", "ios", "android", "api", "solutions architect",
    "software architect", "tech lead", "engineering manager",
]

TECH_TITLE_DENY = [
    "recruiter", "talent acquisition", "talent scout",
    "tutor", "teacher", "administrative assistant", "admin assistant",
    "office administrator", "virtual assistant", "executive assistant",
    "customer support", "customer service", "support agent", "help desk",
    "helpdesk", "sales", "account executive", "business development",
    "nurse", "clinical", "physician", "marketing", "accountant", "accounting",
    "bookkeeper", "data entry", "transcription", "transcriber", "moderator",
    "content writer", "copywriter", "social media", "call center", "chat support",
]

ENTRY_TITLE_ALLOW = [
    "virtual assistant", "administrative assistant", "admin assistant",
    "executive assistant", "office administrator", "data entry",
    "annotation", "annotator", "data annotator", "transcription",
    "transcriber", "transcriptionist", "moderator", "content moderator",
    "content writer", "copywriter", "customer support", "customer service",
    "support agent", "chat support", "call center", "help desk", "helpdesk",
    "technical support", "it support", "bookkeeper", "bookkeeping",
    "scheduler", "scheduling", "tutor", "online tutor", "evaluator",
    "reviewer", "labeler", "labeller", "prompt", "search engine evaluator",
    "social media", "community manager", "researcher",
]

ENTRY_TITLE_DENY = [
    "senior", "lead", "manager", "director", "head of", "vp", "chief",
    "nurse", "clinical", "physician", "surgeon", "driver", "warehouse",
    "cleaner", "security guard", "cook", "chef", "waiter", "waitress",
    "laborer", "electrician", "plumber", "mechanic",
]

# Visa audience targets the same role families as tech, but rejects agency spam.
VISA_TITLE_ALLOW = list(TECH_TITLE_ALLOW)
VISA_TITLE_DENY = TECH_TITLE_DENY + ["staffing agency", "recruitment agency"]

SENIORITY_DENY = {
    "tech": ["principal", "staff", "distinguished", "director", "vp",
             "vice president", "head of", "chief", "cto", "ceo", "cfo"],
    "entry": ["senior", "lead", "manager", "director", "vp", "head of",
              "chief", "principal"],
    "visa": ["principal", "staff", "distinguished", "director", "vp",
             "vice president", "head of", "chief"],
}

GENERIC_DENY = [
    "talent community", "join our talent", "general application",
    "general upwork application", "campus", "student program",
    "student intern", "diversity internship", "early career",
    "open application", "speculative application", "future opportunities",
    "talent pool", "talent pipeline",
]

# Substrings that mark a description as a board stub rather than real content.
BOILERPLATE_DESCRIPTION_MARKERS = [
    "found via web search", "no description", "see job posting",
    "apply on the company website", "via searxng",
]

WAGE_FLOOR_DEFAULT = 4.0
# Per-task pay must be below this fraction of the hourly floor to be dropped
# on wage grounds alone (conservative: legitimate per-task gig work survives).
PER_TASK_MIN_FRACTION = 0.25


@lru_cache(maxsize=None)
def _compile(terms: tuple[str, ...]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b",
                      re.IGNORECASE)


def match_any(text: str, terms: list[str] | tuple[str, ...]) -> str | None:
    """Return the first allow/deny term found in ``text`` (word-boundary), else None."""
    if not text or not terms:
        return None
    m = _compile(tuple(terms)).search(text)
    return m.group(0) if m else None
```

- [ ] **Step 4: Run the tests, confirm green.** Commit: `feat(job-hunter): add audience_rules gate lists`.

## Task 2.2 — Config: `audiences:` block + `wage_floor_usd_per_hour`

**Files:** modify `job_hunter/config.py`; create `tests/test_audience_config.py`.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_audience_config.py
from pathlib import Path
from job_hunter.config import Config, AudiencesConfig
from job_hunter import audience_rules as ar

def test_defaults_come_from_audience_rules():
    c = Config()
    assert c.wage_floor_usd_per_hour == 4.0
    assert c.audiences.tech.title_allow == ar.TECH_TITLE_ALLOW
    assert c.audiences.entry.require_company_or_description is True
    assert c.audiences.tech.require_company is True
    assert c.audiences.visa.require_description is True

def test_production_config_audiences_match_defaults():
    cfg_path = Path(__file__).resolve().parents[1] / "config.production.yaml"
    import yaml
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg = Config(**data)
    assert cfg.audiences == AudiencesConfig()
```

- [ ] **Step 2: Run, confirm failure.**

- [ ] **Step 3: Implement** in `config.py` (add near the other config models; `Config` gains two fields):

```python
from job_hunter import audience_rules as _rules

class AudienceRules(BaseModel):
    title_allow: list[str] = Field(default_factory=list)
    title_deny: list[str] = Field(default_factory=list)
    seniority_deny: list[str] = Field(default_factory=list)
    generic_deny: list[str] = Field(default_factory=list)
    require_company: bool = False
    require_description: bool = False
    require_company_or_description: bool = False
    min_description_chars: int = 40

class AudiencesConfig(BaseModel):
    tech: AudienceRules = Field(default_factory=lambda: AudienceRules(
        title_allow=_rules.TECH_TITLE_ALLOW, title_deny=_rules.TECH_TITLE_DENY,
        seniority_deny=_rules.SENIORITY_DENY["tech"], generic_deny=_rules.GENERIC_DENY,
        require_company=True, require_description=True,
    ))
    entry: AudienceRules = Field(default_factory=lambda: AudienceRules(
        title_allow=_rules.ENTRY_TITLE_ALLOW, title_deny=_rules.ENTRY_TITLE_DENY,
        seniority_deny=_rules.SENIORITY_DENY["entry"], generic_deny=_rules.GENERIC_DENY,
        require_company_or_description=True,
    ))
    visa: AudienceRules = Field(default_factory=lambda: AudienceRules(
        title_allow=_rules.VISA_TITLE_ALLOW, title_deny=_rules.VISA_TITLE_DENY,
        seniority_deny=_rules.SENIORITY_DENY["visa"], generic_deny=_rules.GENERIC_DENY,
        require_description=True,
    ))
```

  and on `Config`:

```python
    audiences: AudiencesConfig = Field(default_factory=AudiencesConfig)
    wage_floor_usd_per_hour: float = 4.0
```

- [ ] **Step 4: Run the tests, confirm green.** Commit: `feat(job-hunter): add audiences config block and wage floor`.

---
## Task 2.3 — `job_hunter/relevance.py` (routing + gates)

**Files:** create `job_hunter/relevance.py`; create `tests/test_relevance.py`.

- [ ] **Step 1: Write the failing tests.** These are the spec's §6 routing fixtures.

```python
# tests/test_relevance.py
from job_hunter.config import Config
from job_hunter.models import Job
from job_hunter import relevance

LONG = "We build products for teams worldwide. " * 3

def job(**kw):
    base = dict(title="Software Engineer", company="Acme", url="https://x/1",
                board="himalayas", location="Remote", remote="Remote",
                description=LONG, tags="")
    base.update(kw)
    return Job(**base)

def classify(j, cfg=None):
    return relevance.classify(j, cfg or Config())

def test_wrong_country_recruiter_is_dropped():
    c = classify(job(title="Remote Recruiter",
                     description="Based in Ciudad de México, CDMX. " + LONG))
    assert c.audience is None

def test_real_tech_role_routes_to_tech():
    c = classify(job(title="Senior Software Engineer"))
    assert c.audience == "tech" and c.score > 0 and c.reasons

def test_entry_va_routes_to_entry_without_company():
    c = classify(job(title="Virtual Assistant", company="", board="indeed_search",
                     description="Support the team with scheduling."))
    assert c.audience == "entry"

def test_visa_posting_routes_to_visa():
    c = classify(job(title="Senior Backend Engineer", board="visa_sponsorship",
                     description="We offer visa sponsorship and relocation support. " + LONG))
    assert c.audience == "visa"

def test_scam_is_dropped():
    assert classify(job(title="Data Entry Clerk", company="",
                        description="Unpaid internship, no experience needed.")).audience is None

def test_metadata_thin_tech_is_dropped_not_routed_to_entry():
    # tech family title, but no company and no real description -> fails tech,
    # fails entry (title not in entry allow) -> dropped.
    assert classify(job(title="Backend Engineer", company="", description="")).audience is None

def test_admin_assistant_kept_for_entry_dropped_for_tech():
    j = job(title="Administrative Assistant", company="", board="indeed_search",
            description="Manage calendars and email.")
    assert classify(j).audience == "entry"

def test_legacy_audience_normalization():
    assert relevance.normalize_audience("gig") == "entry"
    assert relevance.normalize_audience("creative") == "entry"
    assert relevance.normalize_audience("tech") == "tech"
    assert relevance.normalize_audience("") == ""

def test_priority_visa_beats_tech():
    j = job(title="Senior Software Engineer", board="visa_sponsorship",
            description="Relocation and visa sponsorship provided. " + LONG)
    assert classify(j).audience == "visa"

def test_poverty_wage_hourly_is_dropped():
    j = job(title="Virtual Assistant", company="", board="indeed_search",
            description="Pay is $2/hr. " + LONG)
    assert classify(j).audience is None

# --- Review Focus cases -------------------------------------------------

def test_overlapping_title_routes_to_tech_not_entry():
    # "technical support" is an entry family, "engineer" a tech family;
    # the fixed priority (tech before entry) must win.
    assert classify(job(title="Technical Support Engineer", company="Acme")).audience == "tech"

def test_annual_salary_is_not_treated_as_hourly():
    j = job(title="Senior Software Engineer",
            description="Compensation: $120,000 per year. " + LONG)
    assert classify(j).audience == "tech"

def test_visa_board_country_restriction_does_not_block_sponsorship():
    j = job(title="Senior Backend Engineer", board="visa_sponsorship",
            location="Remote (US only)",
            description="We provide visa sponsorship and relocation. " + LONG)
    assert classify(j).audience == "visa"

def test_missing_url_is_dropped():
    assert classify(job(title="Software Engineer", url="")).audience is None
```

- [ ] **Step 2: Run, confirm failure** (the module does not exist yet).

- [ ] **Step 3: Implement.**

```python
# job_hunter/relevance.py
"""Audience routing and per-audience hard gates.

One entry point, :func:`classify`, decides which of the three audiences a job
belongs to (``visa`` -> ``tech`` -> ``entry``), or drops it. The board a job
came from is never the decision; it only informs scoring via ``job.board``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from job_hunter import audience_rules as rules
from job_hunter import eligibility, scoring
from job_hunter.boards.scam_filter import is_unreliable
from job_hunter.config import AudienceRules, Config
from job_hunter.models import Job

AUDIENCE_ORDER = ("visa", "tech", "entry")
CANONICAL_AUDIENCES = ("tech", "entry", "visa")
_LEGACY_AUDIENCE = {"gig": "entry", "creative": "entry"}

_HOURLY_RATE_RE = re.compile(
    r"(?:\$|usd\s*)\s*(\d+(?:[.,]\d+)?)\s*(?:/|per\s*)?\s*(?:hour|hr|h)\b",
    re.IGNORECASE,
)
_PER_TASK_RE = re.compile(
    r"(?:\$|usd\s*)\s*(\d+(?:[.,]\d+)?)\s*(?:/|per\s*)?\s*(?:task|assignment)\b",
    re.IGNORECASE,
)


def normalize_audience(tag: str) -> str:
    """Map any legacy/board audience tag to a canonical one (or '')."""
    t = (tag or "").strip().lower()
    t = _LEGACY_AUDIENCE.get(t, t)
    return t if t in CANONICAL_AUDIENCES else ""


@dataclass
class Classification:
    audience: str | None
    note: str
    score: int = 0
    reasons: str = ""


def _real_description(job: Job, min_chars: int) -> bool:
    desc = (job.description or "").strip()
    if len(desc) < min_chars:
        return False
    low = desc.lower()
    return not any(m in low for m in rules.BOILERPLATE_DESCRIPTION_MARKERS)


def metadata_ok(job: Job, r: AudienceRules) -> tuple[bool, str]:
    has_company = bool((job.company or "").strip())
    has_desc = _real_description(job, r.min_description_chars)
    if not (job.url or "").startswith("http"):
        return False, "no usable URL"
    if r.require_company and not has_company:
        return False, "no company name"
    if r.require_description and not has_desc:
        return False, "no real description"
    if r.require_company_or_description and not (has_company or has_desc):
        return False, "no company or description"
    return True, "metadata ok"


def wage_ok(job: Job, floor: float) -> tuple[bool, str]:
    """Drop only *clearly* below-floor pay. No detectable rate -> keep."""
    blob = f"{job.title} {job.description}"
    m = _HOURLY_RATE_RE.search(blob)
    if m:
        rate = float(m.group(1).replace(",", "."))
        if rate < floor:
            return False, f"hourly rate ${rate:g} below floor ${floor:g}"
        return True, "hourly rate ok"
    m = _PER_TASK_RE.search(blob)
    if m:
        rate = float(m.group(1).replace(",", "."))
        if rate < floor * rules.PER_TASK_MIN_FRACTION:
            return False, f"per-task pay ${rate:g} clearly below floor"
    return True, "no detectable rate"


def country_ok(job: Job, audience: str) -> tuple[bool, str]:
    if audience == "visa":
        return eligibility.has_visa_sponsorship(job)
    return eligibility.check_eligibility(job)


def _passes(job: Job, audience: str, r: AudienceRules) -> tuple[bool, str]:
    denied = rules.match_any(job.title, r.title_deny)
    if denied:
        return False, f"denied title term: {denied}"
    if not rules.match_any(job.title, r.title_allow):
        return False, "title not in audience allow-list"
    if rules.match_any(job.title, r.generic_deny):
        return False, "generic posting"
    sen = rules.match_any(job.title, r.seniority_deny)
    if sen:
        return False, f"seniority excluded: {sen}"
    ok, why = country_ok(job, audience)
    if not ok:
        return False, why
    ok, why = metadata_ok(job, r)
    if not ok:
        return False, why
    return True, why


def classify(job: Job, cfg: Config) -> Classification:
    """Return the winning audience + score, or ``audience=None`` if dropped."""
    bad, why = is_unreliable(title=job.title, company=job.company,
                             description=job.description)
    if bad:
        return Classification(None, f"scam: {why}")

    ok, why = wage_ok(job, cfg.wage_floor_usd_per_hour)
    if not ok:
        return Classification(None, f"wage: {why}")

    for audience in AUDIENCE_ORDER:
        r = getattr(cfg.audiences, audience)
        ok, why = _passes(job, audience, r)
        if ok:
            score, reasons = scoring.score_for_audience(job, audience, cfg)
            return Classification(audience, f"audience={audience}; {why}", score, reasons)
    return Classification(None, "no audience gate passed")


# Spec §4.5 names this entry point ``route_and_gate``.
route_and_gate = classify
```

- [ ] **Step 4: Run the tests.** `test_relevance.py` needs `eligibility.has_visa_sponsorship` (Task 2.4) and `scoring.score_for_audience` (Task 2.6). If those are not yet present, implement 2.4 and 2.6 first, then re-run. Commit once green: `feat(job-hunter): add audience routing and hard gates`.

---
## Task 2.4 — Fix the location leak + expose a board-agnostic sponsorship check

**Files:** modify `job_hunter/eligibility.py`; extend `tests/test_eligibility.py`.

The leak (spec §1.5): a board that reports `location: "Remote"` is treated as "no restriction", and title region detection matches codes (AMER/APAC) but not city names. Target case: *"Remote Recruiter – Ciudad de México, CDMX"*.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_eligibility.py`):

```python
class TestCityNameLeak:
    """A bare 'Remote' must not grant worldwide status when the title or
    description names a specific city (the Ciudad de México leak)."""

    @pytest.mark.parametrize("title,desc", [
        ("Remote Recruiter - Ciudad de México, CDMX", ""),
        ("Customer Support (Mexico City)", ""),
        ("Software Engineer", "Our team is based in Bangalore, India."),
        ("Data Analyst", "This role is in Toronto."),
    ])
    def test_named_city_rejected(self, title, desc):
        ok, note = check_eligibility(job(title=title, location="Remote", description=desc))
        assert not ok, (title, note)

    def test_africa_city_still_eligible(self):
        ok, _ = check_eligibility(job(title="Engineer", location="Remote",
                                      description="Our office is in Kigali, Rwanda."))
        assert ok


class TestVisaSponsorshipSignal:
    def test_signal_detected_regardless_of_board(self):
        from job_hunter.eligibility import has_visa_sponsorship
        ok, note = has_visa_sponsorship(
            job(title="Backend Engineer", board="himalayas",
                description="We provide visa sponsorship and relocation support.")
        )
        assert ok

    def test_no_signal_is_false(self):
        from job_hunter.eligibility import has_visa_sponsorship
        ok, _ = has_visa_sponsorship(job(title="Backend Engineer", board="himalayas",
                                        description="Remote role."))
        assert not ok
```

- [ ] **Step 2: Run, confirm failure.**

- [ ] **Step 3: Implement** in `eligibility.py`:

1. Add a city list + compiled regex near the other constants:

```python
# Specific cities. A board-reported bare "Remote" must not be read as
# "no restriction" when one of these appears in the title/description.
CITY_NAMES = [
    "mexico city", "ciudad de mexico", "ciudad de méxico", "cdmx",
    "guadalajara", "monterrey", "new york", "san francisco", "los angeles",
    "seattle", "austin", "boston", "chicago", "denver", "atlanta", "miami",
    "toronto", "vancouver", "montreal", "london", "manchester", "dublin",
    "berlin", "munich", "hamburg", "paris", "lyon", "madrid", "barcelona",
    "lisbon", "porto", "amsterdam", "rotterdam", "brussels", "zurich",
    "geneva", "vienna", "stockholm", "oslo", "copenhagen", "helsinki",
    "warsaw", "krakow", "prague", "budapest", "bucharest", "sofia", "athens",
    "istanbul", "tel aviv", "dubai", "abu dhabi", "riyadh", "doha",
    "bangalore", "bengaluru", "mumbai", "new delhi", "delhi", "hyderabad",
    "pune", "chennai", "gurgaon", "noida", "karachi", "lahore", "dhaka",
    "colombo", "manila", "cebu", "jakarta", "kuala lumpur", "singapore",
    "bangkok", "ho chi minh", "hanoi", "taipei", "hong kong", "shanghai",
    "beijing", "shenzhen", "tokyo", "osaka", "seoul", "sydney", "melbourne",
    "brisbane", "auckland", "wellington", "sao paulo", "são paulo",
    "rio de janeiro", "buenos aires", "bogota", "bogotá", "lima", "santiago",
    "montevideo", "johannesburg", "cape town", "durban", "lagos", "abuja",
    "accra", "cairo", "casablanca",
]
_CITY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in CITY_NAMES) + r")\b", re.IGNORECASE
)
```

2. Extend the title check (line ~225):

```python
def _has_title_region_restriction(title: str) -> bool:
    """Return True if the title contains a region/country code or a city."""
    return bool(_TITLE_REGION_RE.search(title) or _CITY_RE.search(title))
```

3. In `check_eligibility`, replace the early `if not remainder:` return (line ~356) so a bare "Remote" is verified against the title/description:

```python
    if not remainder:
        # Bare "Remote": verify the title/description does not name a place.
        # Africa signals win; a named non-African city means country-restricted.
        blob = f"{job.title} {(job.description or '')[:400]}"
        if _AFRICA_RE.search(blob):
            return True, "remote / Africa signal"
        city = _CITY_RE.search(blob)
        if city:
            return False, f"names a specific place: {city.group(0)[:40]}"
        return True, "remote / no location restriction"
```

4. Add `has_visa_sponsorship` and make `check_visa_sponsorship` a board-scoped wrapper (do **not** change `VISA_POSITIVE`/`VISA_NEGATIVE`):

```python
def has_visa_sponsorship(job: Job) -> tuple[bool, str]:
    """Sponsorship signal, independent of which board produced the job."""
    text = " ".join([job.title, job.tags, job.description]).lower()
    if VISA_NEGATIVE.search(text):
        return False, "sponsorship explicitly not available"
    if not VISA_POSITIVE.search(text):
        return False, "no visa sponsorship signal"
    return True, "employer offers visa sponsorship / relocation"


def check_visa_sponsorship(job: Job) -> tuple[bool, str]:
    """Board-scoped wrapper (kept for backward compatibility)."""
    if job.board != "visa_sponsorship":
        return False, "not a visa-sponsorship listing"
    return has_visa_sponsorship(job)
```

  Leave `matches_keywords()` in place for now — it is deleted in Task 3.3 together with its last caller.

- [ ] **Step 4: Run the full suite; confirm all green** (`python -m pytest -q`). The existing `TestLocationHeuristics` / `TestATSPatterns` cases must still pass — they do because Africa/global checks run before the city check.

- [ ] **Step 5: Commit:** `fix(job-hunter): reject named cities in bare-Remote postings; add board-agnostic sponsorship check`.

## Task 2.5 — Extend `scam_filter` for poverty-wage / pay-to-work

**Files:** modify `job_hunter/boards/scam_filter.py`; create `tests/test_scam_filter.py`.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_scam_filter.py
import pytest
from job_hunter.boards.scam_filter import is_unreliable

@pytest.mark.parametrize("title,desc", [
    ("Data Entry Clerk", "This is an unpaid internship."),
    ("Sales Agent", "Commission only, no base pay."),
    ("Marketing Associate", "100% commission role."),
    ("Business Partner", "Join our multi-level marketing team."),
    ("Assistant", "Small training fee required before you start."),
    ("Assistant", "Registration fee applies."),
    ("Sales Rep", "Commission-only position."),
])
def test_poverty_and_pay_to_work_dropped(title, desc):
    bad, reason = is_unreliable(title=title, company="Acme", description=desc)
    assert bad, (title, desc)

def test_normal_job_is_kept():
    bad, _ = is_unreliable(title="Software Engineer", company="Acme",
                           description="Build services. Competitive salary, paid time off.")
    assert not bad

def test_unpaid_leave_benefit_is_not_a_scam():
    bad, _ = is_unreliable(title="Software Engineer", company="Acme",
                           description="Generous benefits including paid and unpaid leave options.")
    assert not bad
```

- [ ] **Step 2: Run, confirm failure.**

- [ ] **Step 3: Implement.** Append to `UNRELIABLE_TITLE_PATTERNS`:

```python
    # Poverty-wage / pay-to-work bait
    r"unpaid\s+(?:intern|internship|position|role|trial)",
    r"commission[\s-]only",
    r"100%\s+commission",
    r"\bmlm\b",
    r"multi[\s-]level\s+marketing",
    r"pay[\s-]to[\s-]work",
    r"training\s+fee",
    r"registration\s+fee",
    r"sign[\s-]up\s+fee",
```

  and to the `scam_signals` list inside `is_unreliable`:

```python
        "commission only",
        "commission-only",
        "100% commission",
        "multi-level marketing",
        "pay to work",
        "pay-to-work",
        "training fee",
        "registration fee",
        "starter kit",
        "buy your own equipment",
        "unpaid internship",
        "unpaid intern",
        "unpaid position",
```

  The `test_unpaid_leave_benefit_is_not_a_scam` case passes because `"unpaid"` alone is never a signal — only `unpaid intern/internship/position`.

- [ ] **Step 4: Run the tests, confirm green.** Commit: `feat(job-hunter): extend scam filter with poverty-wage and pay-to-work patterns`.

---
## Task 2.6 — `scoring.py`: three audience rankers

**Files:** modify `job_hunter/scoring.py`; extend `tests/test_scoring.py`.

**Back-compat rule:** `score_job(job, skills, seniority="")` keeps its current signature and behavior exactly (it becomes `score_tech(..., role_families=None)`), so the seven existing `test_scoring.py` tests stay green unchanged. Role-family weighting is opt-in via the new `role_families` argument, which only `relevance` passes.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_scoring.py`):

```python
from job_hunter.config import Config
from job_hunter.scoring import score_entry, score_tech, score_visa, score_for_audience


class TestAudienceRankers:
    def test_role_family_raises_tech_score(self):
        j = make_job(title="Software Engineer")
        plain, _ = score_tech(j, skills=[], role_families=None)
        ranked, reasons = score_tech(j, skills=[], role_families=["engineer", "developer"])
        assert ranked > plain
        assert "role family" in reasons

    def test_entry_scores_above_zero_without_any_skills(self):
        j = make_job(title="Virtual Assistant")
        j.board = "indeed_search"
        score, reasons = score_entry(j, Config())
        assert score > 0
        assert reasons

    def test_entry_ranks_known_platform_higher(self):
        a = make_job(title="Virtual Assistant"); a.board = "entry_platforms"
        b = make_job(title="Virtual Assistant"); b.board = "some_unknown_board"
        assert score_entry(a, Config())[0] > score_entry(b, Config())[0]

    def test_visa_rewards_explicit_sponsorship(self):
        j = make_job(title="Backend Engineer",
                     description="We provide visa sponsorship and relocation.")
        j.company = "Acme"
        score, reasons = score_visa(j, skills=[], role_families=["engineer"])
        assert score > 0
        assert "sponsorship" in reasons

    def test_dispatch_matches_direct_call(self):
        cfg = Config()
        j = make_job(title="Software Engineer"); j.company = "Acme"
        assert score_for_audience(j, "tech", cfg) == score_tech(
            j, cfg.profile.skills, cfg.profile.seniority, cfg.audiences.tech.title_allow)
```

- [ ] **Step 2: Run, confirm failure.**

- [ ] **Step 3: Implement.** Add imports (`from job_hunter import audience_rules as rules`, `from job_hunter import eligibility`) and the constants/helpers, then split the old `score_job` body into `score_tech`:

```python
ROLE_FAMILY_POINTS = 30
SPONSORSHIP_POINTS = 20
COMPANY_POINTS = 10

_ENTRY_TIER_A = {"entry_platforms", "wwr_entry", "alignerr", "outlier",
                 "opentrain", "gig_platforms", "workday"}
_ENTRY_TIER_B = {"indeed_entry", "foundthejob", "indeed_search", "remoteok_entry"}


def _skill_points(job: Job, skills: list[str]) -> tuple[int, list[str]]:
    points = 0
    matched: list[str] = []
    title, tags, description = job.title or "", job.tags or "", job.description or ""
    for skill in skills:
        if not skill.strip():
            continue
        pat = _skill_pattern(skill)
        if pat.search(title):
            points += TITLE_MATCH_POINTS
            matched.append(skill)
        elif pat.search(tags):
            points += TAGS_MATCH_POINTS
            matched.append(skill)
        elif pat.search(description):
            points += DESCRIPTION_MATCH_POINTS
            matched.append(skill)
    return min(points, MAX_SKILL_POINTS), matched


def _salary_points(job: Job) -> tuple[int, str | None]:
    if SALARY_MENTION_RE.search(f"{job.title} {job.description}"):
        return 8, "salary mentioned"
    return 0, None


def _recency_points(job: Job) -> tuple[int, str | None]:
    if not job.posted_at:
        return 0, None
    try:
        posted = datetime.fromisoformat(job.posted_at.replace("Z", "+00:00"))
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - posted
        if age <= timedelta(days=2):
            return 6, "posted in last 2 days"
        if age <= timedelta(days=7):
            return 3, "posted this week"
    except (ValueError, TypeError):
        pass
    return 0, None


def score_tech(job: Job, skills: list[str], seniority: str = "",
               role_families: list[str] | None = None) -> tuple[int, str]:
    reasons: list[str] = []
    points = 0
    fam = rules.match_any(job.title or "", role_families) if role_families else None
    if fam:
        points += ROLE_FAMILY_POINTS
        reasons.append(f"role family: {fam}")
    sp, matched = _skill_points(job, skills)
    points += sp
    if matched:
        reasons.append(f"skills: {', '.join(matched[:6])}")
    p, r = _salary_points(job); points += p; reasons += [r] if r else []
    p, r = _recency_points(job); points += p; reasons += [r] if r else []
    sen = (seniority or "").strip().lower()
    title = job.title or ""
    if sen == "senior" and SENIOR_TITLE_RE.search(title):
        points += 6; reasons.append("matches seniority")
    elif sen == "junior" and JUNIOR_TITLE_RE.search(title):
        points += 6; reasons.append("matches seniority")
    elif sen == "senior" and JUNIOR_TITLE_RE.search(title):
        points -= 10; reasons.append("title looks junior")
    elif sen == "junior" and SENIOR_TITLE_RE.search(title):
        points -= 10; reasons.append("title looks senior")
    points = max(0, min(100, points))
    return points, "; ".join(reasons) if reasons else "no profile skills matched"


def score_entry(job: Job, cfg) -> tuple[int, str]:
    """Entry ranker — deliberately NOT CV-skill-driven."""
    reasons: list[str] = []
    points = 0
    board = (job.board or "").lower()
    if rules.match_any(job.title or "", rules.ENTRY_TITLE_ALLOW):
        points += 10; reasons.append("entry role match")
    if board in _ENTRY_TIER_A:
        points += 30; reasons.append("known-good platform")
    elif board in _ENTRY_TIER_B:
        points += 15; reasons.append("established platform")
    p, r = _salary_points(job); points += p; reasons += [r] if r else []
    if (job.company or "").strip():
        points += 10; reasons.append("company identified")
    p, r = _recency_points(job); points += p; reasons += [r] if r else []
    points = max(0, min(100, points))
    return points, "; ".join(reasons) if reasons else "entry role"


def score_visa(job: Job, skills: list[str],
               role_families: list[str] | None = None) -> tuple[int, str]:
    reasons: list[str] = []
    points = 0
    fam = rules.match_any(job.title or "", role_families) if role_families else None
    if fam:
        points += ROLE_FAMILY_POINTS; reasons.append(f"role family: {fam}")
    sp, matched = _skill_points(job, skills)
    points += sp
    if matched:
        reasons.append(f"skills: {', '.join(matched[:6])}")
    text = f"{job.title} {job.tags} {job.description}"
    if eligibility.VISA_POSITIVE.search(text) and re.search(r"relocation|sponsor", text, re.IGNORECASE):
        points += SPONSORSHIP_POINTS; reasons.append("explicit sponsorship/relocation")
    if (job.company or "").strip():
        points += COMPANY_POINTS; reasons.append("company identified")
    p, r = _recency_points(job); points += p; reasons += [r] if r else []
    points = max(0, min(100, points))
    return points, "; ".join(reasons) if reasons else "visa role"


def score_for_audience(job: Job, audience: str, cfg) -> tuple[int, str]:
    if audience == "entry":
        return score_entry(job, cfg)
    if audience == "visa":
        return score_visa(job, cfg.profile.skills, cfg.audiences.visa.title_allow)
    return score_tech(job, cfg.profile.skills, cfg.profile.seniority,
                      cfg.audiences.tech.title_allow)


def score_job(job: Job, skills: list[str], seniority: str = "") -> tuple[int, str]:
    """Legacy entry point — identical to the original skill-based scoring."""
    return score_tech(job, skills, seniority, None)
```

- [ ] **Step 4: Run the full suite** (`python -m pytest -q`) — the seven original `test_scoring.py` tests plus the new ones must pass. Commit: `feat(job-hunter): add per-audience scoring rankers`.

- [ ] **Step 5: Phase 2 checkpoint** — `relevance.classify()` now works end-to-end in isolation. Nothing in the live pipeline calls it yet.

---
# Phase 3 — Pipeline wiring, liveness, cleanup reclassify

**Outcome:** discovery stores only routed, scored jobs; reposts are counted; dead links are soft-marked; the existing database is re-evaluated with `cleanup --reclassify`.

## Task 3.1 — `models.py`: repost counters + link columns

**Files:** modify `job_hunter/models.py`; extend `tests/test_store.py`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_store.py`):

```python
class TestRepost:
    def test_first_insert_is_not_a_repost(self, store):
        store.add_job(make_job(), True, "w")
        row = store.get_job(1)
        assert row["seen_count"] == 1 and row["repost"] == 0

    def test_repeat_see_increments_and_flags(self, store):
        store.add_job(make_job(), True, "w")
        assert store.add_job(make_job(), True, "w") == "exists"   # unchanged contract
        row = store.get_job(1)
        assert row["seen_count"] == 2 and row["repost"] == 1
        assert row["last_seen_at"]

    def test_only_one_row_per_url(self, store):
        store.add_job(make_job(), True, "w")
        store.add_job(make_job(), True, "w")
        assert len(store.list_jobs(eligible_only=False)) == 1
```

- [ ] **Step 2: Run, confirm failure** (columns do not exist yet).

- [ ] **Step 3: Implement.** Add five columns to `SCHEMA` (inside `CREATE TABLE jobs (...)`):

```sql
    seen_count INTEGER DEFAULT 1,
    last_seen_at TEXT DEFAULT '',
    repost INTEGER DEFAULT 0,
    link_status TEXT DEFAULT '',
    link_checked_at TEXT DEFAULT '',
```

  Add matching entries to `Store._MIGRATIONS`:

```python
        "ALTER TABLE jobs ADD COLUMN seen_count INTEGER DEFAULT 1",
        "ALTER TABLE jobs ADD COLUMN last_seen_at TEXT DEFAULT ''",
        "ALTER TABLE jobs ADD COLUMN repost INTEGER DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN link_status TEXT DEFAULT ''",
        "ALTER TABLE jobs ADD COLUMN link_checked_at TEXT DEFAULT ''",
```

  Change the URL-hit branch of `add_job` (currently returns `"exists"` immediately):

```python
        cur = self.conn.execute("SELECT id FROM jobs WHERE url = ?", (job.url,))
        hit = cur.fetchone()
        if hit:
            self.conn.execute(
                "UPDATE jobs SET seen_count = seen_count + 1, last_seen_at = ?, repost = 1 WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), hit["id"]),
            )
            self.conn.commit()
            return "exists"
```

  Leave the INSERT statement unchanged — the new columns take their defaults.

- [ ] **Step 4: Run the suite, confirm green.** Commit: `feat(job-hunter): track reposts and link status on jobs`.

## Task 3.2 — `job_hunter/liveness.py` (reusable link check)

**Files:** create `job_hunter/liveness.py`; modify `job_hunter/validate_links.py`; create `tests/test_liveness.py`.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_liveness.py
from job_hunter.models import Job, Store
from job_hunter import liveness

def _store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.add_job(Job(title="Software Engineer", company="Acme", url="https://x/1",
                  board="himalayas", location="Remote", description="d" * 60), True, "w")
    return s

def test_dead_link_soft_marks_eligible_zero(tmp_path, monkeypatch):
    s = _store(tmp_path)
    async def fake(rows):
        return [{"id": rows[0]["id"], "verdict": "dead", "status": 404, "error": "", "ok": False}]
    monkeypatch.setattr(liveness, "_check_rows", fake)
    res = liveness.mark_dead_new(s.conn.execute("PRAGMA database_list").fetchone()[2], ids=[1])
    assert res["dead"] == 1
    row = s.get_job(1)
    assert row["eligible"] == 0 and "dead" in row["link_status"]

def test_alive_link_kept(tmp_path, monkeypatch):
    s = _store(tmp_path)
    async def fake(rows):
        return [{"id": rows[0]["id"], "verdict": "ok", "status": 200, "error": "", "ok": True}]
    monkeypatch.setattr(liveness, "_check_rows", fake)
    liveness.mark_dead_new(s.conn.execute("PRAGMA database_list").fetchone()[2], ids=[1])
    assert s.get_job(1)["eligible"] == 1

def test_blocked_403_is_not_dead(tmp_path, monkeypatch):
    s = _store(tmp_path)
    async def fake(rows):
        return [{"id": rows[0]["id"], "verdict": "blocked", "status": 403, "error": "", "ok": False}]
    monkeypatch.setattr(liveness, "_check_rows", fake)
    res = liveness.mark_dead_new(s.conn.execute("PRAGMA database_list").fetchone()[2], ids=[1])
    assert res["dead"] == 0 and s.get_job(1)["eligible"] == 1
```

- [ ] **Step 2: Run, confirm failure.**

- [ ] **Step 3: Implement.** Move `check_url` out of `validate_links.py` into `liveness.py` (same body — HEAD then GET fallback, redirect detection, timing) and add:

```python
def _verdict(result: dict) -> str:
    """Classify a check result. Only 404/410 are 'dead' (droppable)."""
    if result.get("ok"):
        return "ok"
    if result.get("status") in (404, 410):
        return "dead"
    if result.get("status") in (403, 429):
        return "blocked"
    if result.get("error") in ("timeout", "ConnectError", "ConnectionError",
                               "ReadTimeout", "ConnectTimeout"):
        return "unreachable"
    return "error"


async def _check_rows(rows) -> list[dict]:
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        async def one(row):
            res = await check_url(client, row["url"], sem)
            return {**res, "id": row["id"], "verdict": _verdict(res)}
        return list(await asyncio.gather(*(one(r) for r in rows)))


def mark_dead_new(db_path: str, ids: list[int] | None = None,
                  limit: int | None = None) -> dict:
    """Check new eligible rows; soft-mark only 404/410 as eligible=0.

    Returns {"checked", "alive", "dead"}. Never deletes.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if ids:
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, url FROM jobs WHERE id IN ({ph}) AND eligible=1 AND status='new'",
            ids,
        ).fetchall()
    else:
        q = ("SELECT id, url FROM jobs WHERE eligible=1 AND status='new' "
             "AND link_status='' ORDER BY id DESC")
        if limit:
            q += f" LIMIT {int(limit)}"
        rows = conn.execute(q).fetchall()

    if not rows:
        conn.close()
        return {"checked": 0, "alive": 0, "dead": 0}

    results = asyncio.run(_check_rows(rows))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    alive = dead = 0
    for r in results:
        verdict = r["verdict"]
        if verdict == "dead":
            dead += 1
            conn.execute(
                "UPDATE jobs SET link_status=?, link_checked_at=?, eligible=0, "
                "eligibility_note = eligibility_note || ? WHERE id = ?",
                (verdict, now, f" [dead link: HTTP {r['status']}]", r["id"]),
            )
        else:
            alive += 1
            conn.execute("UPDATE jobs SET link_status=?, link_checked_at=? WHERE id=?",
                         (verdict, now, r["id"]))
    conn.commit()
    conn.close()
    return {"checked": len(results), "alive": alive, "dead": dead}
```

  In `validate_links.py`, delete its local `check_url` and import instead:

```python
from job_hunter.liveness import check_url, HEADERS, MAX_CONCURRENT
```

  Keep `validate_links`' own reporting loop unchanged.

- [ ] **Step 4: Run the suite, confirm green.** Commit: `feat(job-hunter): add reusable liveness check with soft-marking`.

---
## Task 3.3 — Wire the pipeline to `relevance` and retire `matches_keywords`

**Files:** modify `job_hunter/orchestrator.py`, `job_hunter/dashboard/server.py`, `job_hunter/eligibility.py`, `tests/test_eligibility.py`.

The board→audience maps and the `matches_keywords` call live in **two** places (`orchestrator._run_board` and `dashboard/server._run_board_with_progress`). Both must switch to `relevance.classify` in the same commit that deletes `matches_keywords`, or the dashboard breaks.

**Interfaces:**
- Consumes: `relevance.classify(job, cfg) -> Classification(audience, note, score, reasons)` (Task 2.3).
- Produces: `orchestrator.run_liveness(cfg) -> dict`; `_run_board` result gains `"dropped"` (`"unreliable"` is now the scam subset of drops).

- [ ] **Step 1: Rewire `orchestrator._run_board`.** Delete the `_BOARD_AUDIENCE` dict (lines 49-72) and its imports. Replace the scam/eligibility/keyword/audience/score block (lines 122-152) with:

```python
    added = eligible = duplicates = unreliable = dropped = 0
    for job in jobs:
        cls = relevance.classify(job, cfg)
        if cls.audience is None:
            dropped += 1
            if cls.note.startswith("scam:"):
                unreliable += 1
            continue
        job.audience = cls.audience
        eligible += 1
        result = store.add_job(job, True, cls.note, score=cls.score, score_reasons=cls.reasons)
        if result == "new":
            added += 1
        elif result == "duplicate":
            duplicates += 1

    return {
        "board": name,
        "fetched": len(jobs),
        "eligible": eligible,
        "added": added,
        "duplicates": duplicates,
        "unreliable": unreliable,
        "dropped": dropped,
        "error": None,
    }
```

  Change the module imports to `from job_hunter import relevance` and drop `eligibility, scoring`, `is_unreliable`, and the `AUDIENCE_*` names (now unused here).

- [ ] **Step 2: Add the post-discovery liveness helper.** The event loop must not be running, so call it from the sync wrapper, not inside `discover`:

```python
def run_liveness(cfg: Config) -> dict:
    """Soft-mark dead links on new rows. Never deletes. See spec §4.5 step 7."""
    from job_hunter import liveness
    return liveness.mark_dead_new(cfg.database)


def run_discover(cfg: Config) -> list[dict]:
    results = asyncio.run(discover(cfg))
    run_liveness(cfg)
    return results
```

- [ ] **Step 3: Rewire `dashboard/server._run_board_with_progress`.** Delete its local `_BOARD_AUDIENCE` (lines 137-150) and the `eligibility`/`scoring`/`AUDIENCE_*` imports (lines 134-135); replace the per-job block (lines 180-201) with the same `relevance.classify` loop from Step 1, keeping the `result_queue` progress puts unchanged. Add `"dropped": dropped` to the final `done` payload.

- [ ] **Step 4: Run liveness after dashboard discovery.** In `_run_discovery_thread`, after the thread-drain block and before the summary, add:

```python
        from job_hunter.orchestrator import run_liveness
        try:
            run_liveness(cfg)
        except Exception as exc:
            _discovery_state["last_result"] = {"liveness_error": str(exc)}
```

- [ ] **Step 5: Delete `matches_keywords`.** Remove the function from `job_hunter/eligibility.py`. In `tests/test_eligibility.py`, drop `matches_keywords` from the import on line 3 and delete the whole `TestKeywords` class.

- [ ] **Step 6: Prove nothing still calls it:**

```bash
grep -rn "matches_keywords" job_hunter tests   # expect: no matches
```

- [ ] **Step 7: Run the full suite** (`python -m pytest -q`), confirm green, then commit: `refactor(job-hunter): route discovery through relevance, retire keyword gate`.

## Task 3.4 — `cleanup.reclassify()` + CLI `--reclassify`

**Files:** modify `job_hunter/cleanup.py`, `job_hunter/cli.py`; create `tests/test_reclassify.py`.

**Interfaces:**
- Consumes: `relevance.classify(job, cfg)` (Task 2.3), `Store._MIGRATIONS` columns (Task 3.1), `liveness.mark_dead_new` (Task 3.2).
- Produces: `cleanup.reclassify(db_path, cfg) -> dict` with keys `total, kept, removed, updated, reason_counts`.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_reclassify.py
import sqlite3
from job_hunter.config import Config
from job_hunter.models import Job, Store
from job_hunter import cleanup

LONG = "We build products for teams worldwide. " * 3

def _seed(path):
    s = Store(str(path))
    s.add_job(Job(title="Software Engineer", company="Acme", url="https://x/1",
                  board="himalayas", location="Remote", description=LONG), True, "w")
    s.add_job(Job(title="Virtual Assistant", company="", url="https://x/2",
                  board="indeed_search", location="Remote",
                  description="Support the team with scheduling."), True, "w")
    s.add_job(Job(title="Remote Recruiter", company="Acme", url="https://x/3",
                  board="himalayas", location="Remote",
                  description="Based in Ciudad de Mexico, CDMX. " + LONG), True, "w")
    return s

def test_new_noise_row_is_deleted(tmp_path):
    db = tmp_path / "t.db"; _seed(db)
    stats = cleanup.reclassify(str(db), Config())
    assert stats["removed"] >= 1
    conn = sqlite3.connect(str(db))
    titles = {r[0] for r in conn.execute("SELECT title FROM jobs")}
    assert "Remote Recruiter" not in titles
    assert "Software Engineer" in titles

def test_history_rows_are_never_deleted(tmp_path):
    db = tmp_path / "t.db"; s = _seed(db)
    s.mark(3, "applied")   # the noise row is now history
    cleanup.reclassify(str(db), Config())
    conn = sqlite3.connect(str(db))
    row = conn.execute("SELECT eligible FROM jobs WHERE title='Remote Recruiter'").fetchone()
    assert row is not None and row[0] == 0   # kept, soft-marked

def test_legacy_gig_audience_becomes_entry(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.add_job(Job(title="Virtual Assistant", company="", url="https://x/9",
                  board="indeed_search", location="Remote",
                  description="Support the team with scheduling.",
                  audience="gig"), True, "w")
    cleanup.reclassify(str(db), Config())
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT audience FROM jobs WHERE url='https://x/9'").fetchone()[0] == "entry"

def test_reclassify_is_idempotent(tmp_path):
    db = tmp_path / "t.db"; _seed(db)
    first = cleanup.reclassify(str(db), Config())
    second = cleanup.reclassify(str(db), Config())
    assert second["removed"] == 0
    assert second["kept"] == first["kept"]

def test_blank_audience_history_row_survives(tmp_path):
    # Review Focus #5: a blank/legacy-audience row that is already history
    # must never be deleted and must never keep a retired audience value.
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.add_job(Job(title="Remote Recruiter", company="Acme", url="https://x/8",
                  board="himalayas", location="Remote",
                  description="Based in Ciudad de Mexico, CDMX. " + LONG,
                  audience=""), True, "w")
    s.mark(1, "hidden")
    cleanup.reclassify(str(db), Config())
    conn = sqlite3.connect(str(db))
    row = conn.execute("SELECT audience, eligible FROM jobs WHERE url='https://x/8'").fetchone()
    assert row is not None                              # never deleted
    assert row[0] in ("", "tech", "entry", "visa")      # never a legacy value
```

- [ ] **Step 2: Run, confirm failure.**

- [ ] **Step 3: Implement `reclassify`** in `cleanup.py`:

```python
def reclassify(db_path: str, cfg) -> dict:
    """Re-derive audience/score for every row; delete only status='new' failures.

    History rows (applied/hidden/skipped) are re-scored but never deleted —
    failures are soft-marked eligible=0. See spec §4.6.
    """
    from job_hunter import relevance
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # One-time legacy normalization; blanks are re-derived below.
    conn.execute("UPDATE jobs SET audience='entry' WHERE audience IN ('gig','creative')")
    rows = conn.execute("SELECT * FROM jobs").fetchall()
    stats = {"total": len(rows), "kept": 0, "removed": 0, "updated": 0, "reason_counts": {}}
    for row in rows:
        job = _row_to_job(row)
        cls = relevance.classify(job, cfg)
        if cls.audience is None:
            reason = cls.note.split(":")[0]
            stats["reason_counts"][reason] = stats["reason_counts"].get(reason, 0) + 1
            if (row["status"] or "new") == "new":
                conn.execute("DELETE FROM jobs WHERE id=?", (row["id"],))
                stats["removed"] += 1
            else:
                conn.execute(
                    "UPDATE jobs SET eligible=0, eligibility_note=? WHERE id=?",
                    (f"[reclassified] {cls.note}", row["id"]),
                )
            continue
        conn.execute(
            "UPDATE jobs SET audience=?, score=?, score_reasons=?, eligible=1, "
            "eligibility_note=? WHERE id=?",
            (cls.audience, cls.score, cls.reasons, cls.note, row["id"]),
        )
        stats["kept"] += 1
        stats["updated"] += 1
    conn.commit()
    conn.close()
    return stats
```

- [ ] **Step 4: Run the tests, confirm green.** Commit: `feat(job-hunter): add cleanup.reclassify for the existing database`.

- [ ] **Step 5: Add the CLI flag.** In `cli.py`, add to the `cleanup` command signature:

```python
    reclassify: bool = typer.Option(False, "--reclassify",
                                    help="Re-derive audience/gates/score for existing rows"),
```

  and, before the normal `full_cleanup` path:

```python
    if reclassify:
        from job_hunter import cleanup as _cleanup
        from job_hunter import liveness
        stats = _cleanup.reclassify(cfg.database, cfg)
        dupes = _cleanup.deduplicate(cfg.database)
        live = liveness.mark_dead_new(cfg.database)
        print("Reclassify complete:")
        print(f"  Re-derived/kept: {stats['kept']}")
        print(f"  Deleted (new):   {stats['removed']}")
        print(f"  Duplicates:      {dupes}")
        print(f"  Dead links:      {live['dead']} of {live['checked']} checked")
        return
```

- [ ] **Step 6: Smoke-test on a throwaway copy of the live DB** (never the live file):

```bash
cp data/jobs.db /tmp/jobs_copy.db
python -c "from job_hunter.config import Config; from job_hunter import cleanup; print(cleanup.reclassify('/tmp/jobs_copy.db', Config()))"
```

  Expect a large `removed` count and three non-empty audiences. Commit: `feat(job-hunter): add cleanup --reclassify CLI`.

## Task 3.5 — Collapse the dashboard to Tech / Entry / Visa

**Files:** modify `job_hunter/dashboard/server.py`, `templates/{jobs,home,platforms,detail}.html`.

**Interfaces:**
- Consumes: the `audience` column now only ever holds `tech|entry|visa` (Tasks 3.3/3.4).
- Produces: `platforms.html` context gains `visa_jobs`; loses `creative_jobs`.

- [ ] **Step 1: Fix `server.py` audience SQL.** Replace both `CASE WHEN audience='entry' THEN 0 ... ELSE 4 END` expressions (home query ~line 294 and `_query_jobs` ~line 592) with:

```sql
CASE audience WHEN 'tech' THEN 0 WHEN 'entry' THEN 1 WHEN 'visa' THEN 2 ELSE 3 END
```

  In `platforms_page`, drop the `creative_jobs` query and add:

```python
        visa_jobs = conn.execute(
            "SELECT * FROM jobs WHERE eligible=1 AND audience='visa' ORDER BY found_at DESC LIMIT 30"
        ).fetchall()
```

  Pass `"visa_jobs": visa_jobs` and remove `"creative_jobs"` from the template context.

- [ ] **Step 2: Update `BOARD_REGISTRY` audience labels** so no board advertises a retired audience: `opentrain`, `gig_platforms`, `indeed` → `"entry"`; `visa_sponsorship` stays `"visa"`. (Display metadata only — routing ignores it.)

- [ ] **Step 3: `jobs.html`** — drop the `creative` and `gig` `<option>`s from the audience `<select>` (lines 34-35). Add a repost badge and link-status marker to the card header:

```html
{% if job.repost %}<span class="badge badge-board" title="seen {{ job.seen_count }}×">♻ repost</span>{% endif %}
{% if job.link_status and job.link_status != 'ok' %}<span class="badge badge-hidden">⚠ {{ job.link_status }}</span>{% endif %}
```

- [ ] **Step 4: `home.html`** — in the audience bar chart (lines 85-100), drop the `creative`/`gig` branches; add `{% elif aud == 'visa' %}🛂 Visa` with its own colour. Keep the `else` branch for any stray value.

- [ ] **Step 5: `platforms.html`** — replace the five tabs (lines 10-16) with three: `tech`, `entry`, `visa`; delete the Gig and Creative tab bodies; add a Visa tab body listing `visa_jobs` (same card markup as the Tech tab). Update the `showTab` default to `'tech'`.

- [ ] **Step 6: `detail.html`** — audience and `score_reasons` are already shown. Add repost/link rows to the Metadata table:

```html
{% if job.seen_count and job.seen_count > 1 %}
<tr><td style="color: var(--text-muted);">Seen</td><td>{{ job.seen_count }}× (repost)</td></tr>
{% endif %}
{% if job.link_status %}
<tr><td style="color: var(--text-muted);">Link</td><td>{{ job.link_status }}</td></tr>
{% endif %}
```

- [ ] **Step 7: Render every page against a reclassified DB copy** and confirm no `gig`/`creative` string appears and all three tabs populate:

```bash
python -m job_hunter.dashboard.server   # then open http://127.0.0.1:8000
```

  Commit: `feat(job-hunter): collapse dashboard to tech/entry/visa views`.

---
# Phase 4 — Documentation, integration test, deploy

**Outcome:** the new model is documented, proven end-to-end over a fixture DB, and running on the VPS with three populated views.

## Task 4.1 — README

**Files:** modify `README.md`.

- [ ] **Step 1:** Replace the keyword paragraph in "How eligibility works" (lines 49-52) with the three-audience model, and append a "Production config" section:

````markdown
## Relevance: three audiences

Every stored job is routed to exactly one audience — `tech`, `entry`, or
`visa` — by `job_hunter/relevance.py` (priority visa → tech → entry; a job
that passes none is dropped). The board it came from is only a hint. The
global `keywords` gate is retired; per-audience title allow-lists are the
filter. Each audience has its own hard gates (title, seniority, metadata,
country) and its own 0-100 ranker.

## Production config

The container mounts `config.production.yaml` read-only over `/app/config.yaml`.
Its `profile:` block is generated from the `career-ops` project:

```bash
python scripts/sync_profile.py            # regenerate from ../career-ops
python scripts/sync_profile.py --check     # fail if stale (CI)
```

After deploying new rules, re-evaluate the existing database once:

```bash
python -m job_hunter cleanup --reclassify --yes
```
````

- [ ] **Step 2:** Commit: `docs(job-hunter): document audiences and production config`.

## Task 4.2 — Integration test over a fixture DB

**Files:** create `tests/test_integration_relevance.py`.

- [ ] **Step 1: Write the test** (the spec's §6 "Integration" item):

```python
# tests/test_integration_relevance.py
import sqlite3
from job_hunter.config import Config
from job_hunter.models import Job, Store
from job_hunter import cleanup

LONG = "We build products for teams worldwide. " * 3

def test_router_splits_fixture_db(tmp_path):
    db = tmp_path / "t.db"
    s = Store(str(db))
    s.add_job(Job(title="Senior Software Engineer", company="Acme", url="https://x/1",
                  board="himalayas", location="Remote", description=LONG), True, "w")
    s.add_job(Job(title="Virtual Assistant", company="", url="https://x/2",
                  board="indeed_search", location="Remote",
                  description="Support the team with scheduling."), True, "w")
    s.add_job(Job(title="Senior Backend Engineer", company="Acme", url="https://x/3",
                  board="visa_sponsorship", location="",
                  description="We offer visa sponsorship and relocation. " + LONG), True, "w")
    s.add_job(Job(title="Remote Recruiter", company="Acme", url="https://x/4",
                  board="himalayas", location="Remote",
                  description="Based in Ciudad de Mexico, CDMX. " + LONG), True, "w")
    cleanup.reclassify(str(db), Config())
    conn = sqlite3.connect(str(db))
    auds = {r[0] for r in conn.execute("SELECT DISTINCT audience FROM jobs")}
    assert auds <= {"tech", "entry", "visa"}
    counts = dict(conn.execute("SELECT audience, COUNT(*) FROM jobs GROUP BY audience"))
    assert counts.get("tech", 0) >= 1
    assert counts.get("entry", 0) >= 1
    assert counts.get("visa", 0) >= 1
    assert conn.execute("SELECT COUNT(*) FROM jobs WHERE title='Remote Recruiter'").fetchone()[0] == 0
```

- [ ] **Step 2: Run the whole suite** (`python -m pytest -q`), all green. Commit: `test(job-hunter): add end-to-end relevance integration test`.

## Task 4.3 — Deploy and verify on the VPS

- [ ] **Step 1:** Push and pull:

```bash
git push origin feat/opportunity-categories
# VPS
cd /root/job-hunter && git pull
cd job-hunter && docker compose up -d --build
```

- [ ] **Step 2: Confirm the real profile + mounted config:**

```bash
docker exec job-hunter md5sum /app/config.yaml
docker exec job-hunter python -c "from job_hunter.config import load_config; c=load_config(); print(c.profile.name, c.profile.skills[:5])"
```

- [ ] **Step 3: Reclassify once** and record before/after:

```bash
docker exec job-hunter python -c "import sqlite3;c=sqlite3.connect('/app/data/jobs.db');print('before',c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])"
docker exec job-hunter python -m job_hunter cleanup --reclassify --yes
docker exec job-hunter python -c "import sqlite3;c=sqlite3.connect('/app/data/jobs.db');print(list(c.execute('SELECT audience,COUNT(*) FROM jobs WHERE eligible=1 GROUP BY audience')))"
```

- [ ] **Step 4: Verify acceptance criteria (spec §8):** three populated dashboard views at `http://72.60.188.94:8001/jobs`, no degenerate 0-score wall, no `gig`/`creative` anywhere, and `applied`/`hidden`/`skipped` rows still present:

```bash
docker exec job-hunter python -c "import sqlite3;c=sqlite3.connect('/app/data/jobs.db');print(list(c.execute('SELECT status,COUNT(*) FROM jobs GROUP BY status')))"
```

- [ ] **Step 5:** Note any deviation from the spec in the relevant commit message; do not silently widen scope.

---

## Self-Review (plan author)

- **Spec coverage:** §1.1–1.5 root cause → Tasks 1.1–1.4, 2.4; §4.2 routing → 2.3; §4.3 gates → 2.1/2.2/2.3/2.4/2.5; §4.4 scoring → 2.6; §4.5 wiring → 3.1/3.2/3.3; §4.6 re-eval → 3.4; §4.7 dashboard → 3.5; §5 data model → 3.1; §6 tests → every task + 4.2; §7 deploy → 1.4/4.3; §8 acceptance → 4.3.
- **Retired cleanly:** `matches_keywords` + `TestKeywords` (3.3), both `_BOARD_AUDIENCE` maps (3.3), `creative`/`gig` in the UI (3.5).
- **Back-compat held:** `score_job` keeps its signature and behavior (2.6); `add_job` still returns `"exists"` on a URL hit (3.1); existing `test_scoring.py`/`test_store.py`/`test_eligibility.py` cases stay green.
- **Review Focus tests placed:** Task 2.3 gains overlapping-title, annual-salary, visa-board-with-restriction, and empty-URL cases; Task 3.4 gains the blank/legacy history-row case.
- **Type consistency checked:** `Classification(audience, note, score, reasons)`, `relevance.classify(job, cfg)`, `scoring.score_for_audience(job, audience, cfg)`, `liveness.mark_dead_new(db_path, ids=None, limit=None)`, `cleanup.reclassify(db_path, cfg)` are named identically everywhere they are used.

