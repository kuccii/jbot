"""Rwanda eligibility rules.

A job is eligible if it can realistically be done from Rwanda:
  1. The board gave an explicit eligible-country/region list (e.g. Remote4Africa)
     -> eligible iff "Rwanda" is listed, OR a broader region that includes
        Rwanda is listed ("Africa", "East Africa", "EMEA", "Worldwide", ...).
        NOT eligible if the list names only specific other countries.
  2. Otherwise we infer from the location/region text. The location is judged
     after stripping remote-flavored words ("remote", "fully remote", ...):
     -> eligible if what remains is empty (location was only "remote"), or
        names Africa / East Africa / Rwanda / Kigali / EMEA, or a worldwide
        region ("worldwide", "global", "anywhere", ...).
     -> NOT eligible if what remains names a specific place ("Remote, Italy",
        "New York", "APAC", "Remote (UK)", ...) or a physical-role signal
        ("onsite", "hybrid", "in-person", ...).
  3. RemoteOK's feed mixes in physical/onsite roles, so a bare city location
     is NOT treated as eligible — only remote/worldwide/Africa signals (or an
     empty location) pass.
"""

from __future__ import annotations

import re

from job_hunter.models import Job

# Remote-flavored words stripped before judging the remaining location text.
REMOTE_WORDS = [
    "100% remote", "fully remote", "work from anywhere", "remote-first",
    "remote", "remoto", "telecommute", "telework",
]

# Words that mean "open to anyone, anywhere".
GLOBAL = [
    "anywhere", "worldwide", "global", "any country", "all countries",
    "🌏", "international", "emea", "middle east and africa",
]

# Physical-role / country-restriction signals in the remaining text.
RESTRICTED = [
    "onsite", "on-site", "in-person", "hybrid", "must be based in",
    "must be located", "must reside", "based in", "only",
    "usa", "united states", "u.s.", "canada", "united kingdom",
    "europe", "eu only", "european union", "apac", "latam", "nordics",
    "italy", "germany", "france", "spain", "netherlands", "poland",
    "portugal", "belgium", "austria", "switzerland", "sweden", "norway",
    "denmark", "finland", "ireland", "greece", "ukraine", "romania",
    "czech", "hungary", "bulgaria", "croatia", "serbia", "slovakia",
    "slovenia", "estonia", "latvia", "lithuania", "luxembourg", "iceland",
    "malta", "cyprus", "russia", "belarus", "kazakhstan",
    "mexico", "brazil", "argentina", "colombia", "chile", "peru",
    "india", "pakistan", "bangladesh", "sri lanka", "china", "hong kong",
    "taiwan", "japan", "south korea", "vietnam", "thailand", "philippines",
    "indonesia", "malaysia", "singapore", "australia", "new zealand",
    "uae", "dubai", "israel", "turkey", "saudi arabia", "qatar",
    "kuwait", "bahrain", "oman", "jordan", "lebanon", "egypt",
    "new york", "san francisco", "london", "berlin", "paris", "amsterdam",
    "cardiff", "sydney", "melbourne", "toronto", "austin", "seattle",
    "los angeles", "chicago", "boston", "singapore", "tokyo", "bengaluru",
    "bangalore", "mumbai", "lagos", "nairobi", "accra", "cairo", "joburg",
    "cape town", "dubai", "riyadh", "kigali",
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

_REMOTE_WORDS_RE = re.compile(
    r"|".join(re.escape(w) for w in REMOTE_WORDS), re.IGNORECASE
)
_GLOBAL_RE = re.compile(
    r"|".join(re.escape(w) for w in GLOBAL), re.IGNORECASE
)
_AFRICA_RE = re.compile(
    r"|".join(re.escape(w) for w in AFRICA), re.IGNORECASE
)
_RESTRICTED_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in RESTRICTED) + r")\b", re.IGNORECASE
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

    # Strip remote-flavored words, then judge whatever place remains:
    #   "Remote"               -> ""           -> eligible
    #   "Remote, Italy"        -> "italy"      -> not eligible
    #   "New York, NY Remote"  -> "new york ny" -> not eligible
    #   "Remote, Worldwide"    -> "worldwide"  -> eligible
    #   "Remote, EMEA"         -> "emea"       -> eligible
    remainder = _REMOTE_WORDS_RE.sub(" ", loc)
    remainder = " ".join(remainder.split())

    if not remainder:
        return True, "remote / no location restriction"

    if _AFRICA_RE.search(remainder):
        return True, f"location mentions Africa/East Africa: {loc[:60]}"

    if _GLOBAL_RE.search(remainder):
        return True, f"worldwide: {loc[:60]}"

    if _RESTRICTED_RE.search(remainder):
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
