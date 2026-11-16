"""Canonical gate lists for the three audiences.

Single source of truth. ``config.production.yaml`` carries an ``audiences:``
block that can override any list; an empty block inherits these defaults.
"""
from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=None)
def _compile(terms: tuple[str, ...]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b",
                      re.IGNORECASE)


def match_any(text: str, terms: list[str] | tuple[str, ...]) -> str | None:
    """Return the first allow/deny term found in ``text`` (word-boundary), else None."""
    if not text or not terms:
        return None
    m = _compile(tuple(terms)).search(text)
    return m.group(0).lower() if m else None


# ---------------------------------------------------------------------------
# Tech audience — role families that are clearly technical
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Tech audience — titles that are clearly NOT technical (off‑profile)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Entry audience — role families that are clearly entry-level / gig / online
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Entry audience — titles that are clearly NOT entry-level (off‑profile)
# ---------------------------------------------------------------------------
ENTRY_TITLE_DENY = [
    "senior", "lead", "manager", "director", "head of", "vp", "chief",
    "nurse", "clinical", "physician", "surgeon", "driver", "warehouse",
    "cleaner", "security guard", "cook", "chef", "waiter", "waitress",
    "laborer", "electrician", "plumber", "mechanic",
]

# ---------------------------------------------------------------------------
# Visa audience — same role families as tech, but rejects agency spam.
# ---------------------------------------------------------------------------
VISA_TITLE_ALLOW = list(TECH_TITLE_ALLOW)

VISA_TITLE_DENY = TECH_TITLE_DENY + ["staffing agency", "recruitment agency"]


# ---------------------------------------------------------------------------
# Seniority denial per-audience.  These are substrings that, if present in a
# title, cause the row to be downgraded or dropped for the given audience.
# ---------------------------------------------------------------------------
SENIORITY_DENY = {
    "tech": ["principal", "staff", "distinguished", "director", "vp",
             "vice president", "head of", "chief", "cto", "ceo", "cfo"],
    "entry": ["senior", "lead", "manager", "director", "vp", "head of",
              "chief", "principal"],
    "visa": ["principal", "staff", "distinguished", "director", "vp",
             "vice president", "head of", "chief"],
}

# ---------------------------------------------------------------------------
# Generic deny list — titles / promotions that are never actionable.
# ---------------------------------------------------------------------------
GENERIC_DENY = [
    "talent community", "join our talent", "general application",
    "general upwork application", "campus", "student program",
    "student intern", "diversity internship", "early career",
    "open application", "speculative application", "future opportunities",
    "talent pool", "talent pipeline",
]

# ---------------------------------------------------------------------------
# Substrings that mark a description as a board stub rather than real content.
# ---------------------------------------------------------------------------
BOILERPLATE_DESCRIPTION_MARKERS = [
    "found via web search", "no description", "see job posting",
    "apply on the company website", "via searxng",
]