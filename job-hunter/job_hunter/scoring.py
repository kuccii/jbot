"""Score jobs against the candidate's profile skills.

Fit scoring is separate from eligibility: eligibility decides whether a job
can be stored at all (can it legally/practically be worked from Rwanda or
Kenya), scoring decides which of the eligible jobs are worth looking at
first. A 0-100 score is computed from how many configured skills appear in
the title/tags/description, with a title match weighted more heavily than a
description-only mention, plus small boosts for signals candidates usually
care about (salary mentioned, freshly posted, matches a top keyword).

Additionally, three audience‑specific rankers are provided:
  ``score_tech``, ``score_entry``, ``score_visa``, and a dispatcher
``score_for_audience``.  Role‑family weighting is opt‑in via the
``role_families`` argument.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from job_hunter.models import Job
from job_hunter import audience_rules as rules
from job_hunter import eligibility

# Points awarded per matched skill, depending on where it was found.
TITLE_MATCH_POINTS = 18
TAGS_MATCH_POINTS = 12
DESCRIPTION_MATCH_POINTS = 6
MAX_SKILL_POINTS = 80  # skills alone cap here; bonuses can push past it

ROLE_FAMILY_POINTS = 30
SPONSORSHIP_POINTS = 20
COMPANY_POINTS = 10

_ENTRY_TIER_A = {"entry_platforms", "wwr_entry", "alignerr", "outlier",
                 "opentrain", "gig_platforms", "workday"}
_ENTRY_TIER_B = {"indeed_entry", "foundthejob", "indeed_search", "remoteok_entry"}

SALARY_MENTION_RE = re.compile(
    r"\$\s?\d{2,3}[,.]?\d{0,3}k?|\bUSD\b|salary range|compensation:", re.IGNORECASE
)
SENIOR_TITLE_RE = re.compile(r"\b(senior|staff|principal|lead)\b", re.IGNORECASE)
JUNIOR_TITLE_RE = re.compile(r"\b(junior|intern|entry.level|graduate)\b", re.IGNORECASE)


def _skill_pattern(skill: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(skill.strip())}\b", re.IGNORECASE)


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
    """Tech audience ranker — skill‑driven with role‑family weighting."""
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
    """Visa audience ranker — skill‑driven plus sponsorship signal."""
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
    """Dispatch to the appropriate audience ranker."""
    if audience == "entry":
        return score_entry(job, cfg)
    if audience == "visa":
        return score_visa(job, cfg.profile.skills, cfg.audiences.visa.title_allow)
    return score_tech(job, cfg.profile.skills, cfg.profile.seniority,
                      cfg.audiences.tech.title_allow)


def score_job(job: Job, skills: list[str], seniority: str = "") -> tuple[int, str]:
    """Legacy entry point — identical to the original skill-based scoring."""
    return score_tech(job, skills, seniority, None)