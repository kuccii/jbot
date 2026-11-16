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
    """Drop only clearly below-floor pay. No detectable rate -> keep."""
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