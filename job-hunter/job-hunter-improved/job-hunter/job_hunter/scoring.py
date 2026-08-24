"""Score jobs against the candidate's profile skills.

Fit scoring is separate from eligibility: eligibility decides whether a job
can be stored at all (can it legally/practically be worked from Rwanda or
Kenya), scoring decides which of the eligible jobs are worth looking at
first. A 0-100 score is computed from how many configured skills appear in
the title/tags/description, with a title match weighted more heavily than a
description-only mention, plus small boosts for signals candidates usually
care about (salary mentioned, freshly posted, matches a top keyword).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from job_hunter.models import Job

# Points awarded per matched skill, depending on where it was found.
TITLE_MATCH_POINTS = 18
TAGS_MATCH_POINTS = 12
DESCRIPTION_MATCH_POINTS = 6
MAX_SKILL_POINTS = 80  # skills alone cap here; bonuses can push past it

SALARY_MENTION_RE = re.compile(
    r"\$\s?\d{2,3}[,\.]?\d{0,3}k?|\bUSD\b|salary range|compensation:", re.IGNORECASE
)
SENIOR_TITLE_RE = re.compile(r"\b(senior|staff|principal|lead)\b", re.IGNORECASE)
JUNIOR_TITLE_RE = re.compile(r"\b(junior|intern|entry.level|graduate)\b", re.IGNORECASE)


def _skill_pattern(skill: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(skill.strip())}\b", re.IGNORECASE)


def score_job(job: Job, skills: list[str], seniority: str = "") -> tuple[int, str]:
    """Return (score 0-100, human-readable reasons string).

    `skills` comes from profile.skills in config.yaml. `seniority`, if set
    to "junior"/"mid"/"senior", nudges the score toward matching titles.
    """
    reasons: list[str] = []
    points = 0
    matched_skills: list[str] = []

    title = job.title or ""
    tags = job.tags or ""
    description = job.description or ""

    for skill in skills:
        if not skill.strip():
            continue
        pat = _skill_pattern(skill)
        if pat.search(title):
            points += TITLE_MATCH_POINTS
            matched_skills.append(skill)
        elif pat.search(tags):
            points += TAGS_MATCH_POINTS
            matched_skills.append(skill)
        elif pat.search(description):
            points += DESCRIPTION_MATCH_POINTS
            matched_skills.append(skill)

    points = min(points, MAX_SKILL_POINTS)
    if matched_skills:
        reasons.append(f"skills: {', '.join(matched_skills[:6])}")

    # Bonus signals.
    if SALARY_MENTION_RE.search(title + " " + description):
        points += 8
        reasons.append("salary mentioned")

    if job.posted_at:
        try:
            posted = datetime.fromisoformat(job.posted_at.replace("Z", "+00:00"))
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - posted <= timedelta(days=2):
                points += 6
                reasons.append("posted in last 2 days")
        except (ValueError, TypeError):
            pass

    seniority = (seniority or "").strip().lower()
    if seniority == "senior" and SENIOR_TITLE_RE.search(title):
        points += 6
        reasons.append("matches seniority")
    elif seniority == "junior" and JUNIOR_TITLE_RE.search(title):
        points += 6
        reasons.append("matches seniority")
    elif seniority == "senior" and JUNIOR_TITLE_RE.search(title):
        points -= 10
        reasons.append("title looks junior")
    elif seniority == "junior" and SENIOR_TITLE_RE.search(title):
        points -= 10
        reasons.append("title looks senior")

    points = max(0, min(100, points))
    return points, "; ".join(reasons) if reasons else "no profile skills matched"
