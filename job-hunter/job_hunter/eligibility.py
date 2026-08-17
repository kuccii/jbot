"""Rwanda eligibility rules.

A job is eligible if it can realistically be done from Rwanda:
  1. The board gave an explicit eligible-country/region list (e.g. Remote4Africa)
     -> eligible iff "Rwanda" is listed, OR a broader region that includes
        Rwanda is listed ("Africa", "East Africa", "EMEA", "Worldwide", ...).
        NOT eligible if the list names only specific other countries.
  2. Otherwise we infer from the location/region text:
     -> eligible if worldwide-remote ("anywhere", "worldwide", "global", "🌏")
        or the location names Africa / East Africa / Rwanda / Kigali.
     -> NOT eligible if the location is explicitly restricted elsewhere
        ("USA only", "Canada", "Europe", "UK only", "onsite", "hybrid", ...).
  3. RemoteOK's feed mixes in physical/onsite roles, so a bare city location
     is NOT treated as eligible — only remote/worldwide/Africa signals (or an
     empty location) pass.
"""

from __future__ import annotations

import re

from job_hunter.models import Job

# Words that mean "restricted to a specific country/region" -> not eligible.
RESTRICTED = [
    "usa", "united states", "u.s.", "us only", "canada", "uk only",
    "united kingdom", "europe", "eu only", "australia", "new zealand",
    "singapore", "japan", "germany only", "france only", "onsite",
    "on-site", "in-person", "hybrid", "must be based in", "must be located",
    "us-based", "based in the us", "european union",
]

# Words that mean "open to anyone, anywhere" -> eligible.
WORLDWIDE = [
    "anywhere", "worldwide", "global", "🌏", "remote", "remoto",
    "fully remote", "100% remote", "work from anywhere", "telecommute",
]

# Africa-related location signals -> eligible.
AFRICA = [
    "rwanda", "kigali", "east africa", "africa", "emea", "middle east and africa",
]

# Regions in an eligible-country list that include Rwanda.
RWANDA_OR_BROADER = [
    "rwanda", "africa", "east africa", "emea", "middle east and africa",
    "sub-saharan africa", "worldwide", "global", "anywhere", "all countries",
    "remote",
]

_RESTRICTED_RE = re.compile(
    r"|".join(re.escape(w) for w in RESTRICTED), re.IGNORECASE
)
_WORLDWIDE_RE = re.compile(
    r"|".join(re.escape(w) for w in WORLDWIDE), re.IGNORECASE
)
_AFRICA_RE = re.compile(
    r"|".join(re.escape(w) for w in AFRICA), re.IGNORECASE
)


def check_eligibility(job: Job) -> tuple[bool, str]:
    """Return (eligible, reason)."""

    # 1. Explicit country/region list from the board (most reliable signal).
    countries = [c.strip() for c in job.eligible_countries if c and c.strip()]
    if countries:
        lowered = [c.lower() for c in countries]
        if "rwanda" in lowered:
            return True, "Rwanda in board's eligible-country list"
        if any(c in RWANDA_OR_BROADER for c in lowered):
            return True, "open to " + ", ".join(countries[:4]) + " (includes Rwanda)"
        return False, "board restricts to: " + ", ".join(countries[:5])

    # 1b. Himalayas uses "Worldwide" as the location text when there are no
    #     restrictions (empty locationRestrictions). Treat that as eligible.
    if job.location and job.location.strip().lower() == "worldwide":
        return True, "worldwide (no location restrictions)"

    # 2. Location-text heuristics.
    loc = (job.location or "") + " " + (job.remote or "")
    if not loc.strip():
        # Remote-only boards with no location signal -> assume open remote.
        if job.board in ("remote4africa", "remoteok"):
            return True, "no location listed (remote board)"
        return False, "unknown location"

    if _WORLDWIDE_RE.search(loc) and not _RESTRICTED_RE.search(loc):
        return True, "remote / worldwide"
    if _AFRICA_RE.search(loc):
        return True, f"location mentions Africa/East Africa: {loc[:60]}"
    if _RESTRICTED_RE.search(loc):
        return False, f"restricted location: {loc[:60]}"

    return False, f"location-specific: {loc[:60]}"


def matches_keywords(job: Job, keywords: list[str]) -> bool:
    """Relevance filter — job must mention at least one configured keyword.

    Boards that provide curated tags (e.g. RemoteOK) match on title + tags.
    Boards without tags match on title + description instead.

    Matching is word-boundary based, so the keyword "ai" matches "AI engineer"
    but not "maintenance" or "virtual assistant".
    """
    if not keywords:
        return True
    if job.tags.strip():
        haystack = f"{job.title} {job.tags}".lower()
    else:
        haystack = f"{job.title} {job.description}".lower()
    patterns = [re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE) for k in keywords]
    return any(p.search(haystack) for p in patterns)
