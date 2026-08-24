"""Rwanda + Kenya eligibility rules.

A job is eligible if it can realistically be done from Rwanda or Kenya:
  1. The board gave an explicit eligible-country/region list (e.g. Remote4Africa)
     -> eligible iff "Rwanda" or "Kenya" is listed, OR a broader region that
        includes them is listed ("Africa", "East Africa", "EMEA", ...).
        NOT eligible if the list names only specific other countries.
  2. Otherwise we infer from the location/region text. The location is judged
     after stripping remote-flavored words ("remote", "fully remote", ...):
     -> eligible if what remains is empty (location was only "remote"), or
        names Africa / East Africa / Rwanda / Kenya / EMEA, or a worldwide
        region ("worldwide", "global", "anywhere", ...).
     -> NOT eligible if what remains names a specific place ("Remote, Italy",
        "New York", "APAC", "Remote (UK)", ...) or a physical-role signal
        ("onsite", "hybrid", "in-person", ...).
  3. RemoteOK's feed mixes in physical/onsite roles, so a bare city location
     is NOT treated as eligible — only remote/worldwide/Africa signals (or an
     empty location) pass.
  4. Title and description are scanned for hidden restrictions:
     -> NOT eligible if title contains region codes (USA, AMER, APAC, etc.)
     -> NOT eligible if description mentions timezone requirements (US hours,
        Eastern Time, must overlap with US business hours, etc.)
     -> NOT eligible for generic postings (General Application, Talent
        Community, Campus programs, Student roles).
     -> NOT eligible if description states "preference towards candidates
        based in [specific region]".
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
# Note: "emea" is handled specially — standalone "EMEA" means the job is
# open to EMEA candidates (eligible), but "Dublin, Ireland, EMEA" means
# the job is in Dublin (not eligible). See _is_emea_only_location().
GLOBAL = [
    "anywhere", "worldwide", "global", "any country", "all countries",
    "🌏", "international", "middle east and africa",
]

# EMEA as a standalone location signal (not attached to a specific city).
EMEA_STANDALONE_RE = re.compile(
    r"^\s*emea\s*$"  # just "EMEA"
    r"|^\s*remote\s*,?\s*emea\s*$"  # "Remote, EMEA"
    r"|^\s*remote\s*-\s*emea\s*$"  # "Remote - EMEA"
    r"|,\s*emea\s*$",  # trailing ", EMEA" but only if no city before it
    re.IGNORECASE,
)


def _is_emea_only_location(loc: str) -> bool:
    """Return True if location is just "EMEA" with no specific city/country.

    "EMEA" alone or "Remote, EMEA" -> True (eligible)
    "Dublin, Ireland, EMEA" -> False (job is in Dublin)
    "Remote - NA, APAC, EMEA" -> False (job lists specific regions)
    """
    stripped = loc.strip()
    low = stripped.lower()
    # Simple cases
    if low in ("emea", "remote emea", "remote, emea", "remote - emea"):
        return True
    # Check if EMEA is the only region-like token (no city/country before it)
    # Remove "remote" variants, then check if only "emea" remains
    cleaned = re.sub(r"\b(remote|remoto)\b", "", low, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" ,-. ")
    return cleaned == "emea"

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
    "bangalore", "mumbai", "lagos", "accra", "cairo", "joburg",
    "cape town", "dubai", "riyadh", "kigali",
]

# Region codes that appear in job titles to indicate geographic restrictions.
# E.g. "Customer Solution Architect (AMER)", "Director of Product Marketing - USA"
TITLE_REGION_CODES = [
    "amer", "americas", "north america", "south america", "latam",
    "apac", "emea", "europe", "uk only", "eu only",
    "usa", "us only", "united states", "canada",
]

# Generic / non-real-job title patterns.
GENERIC_TITLES = [
    "general application", "general upwork application",
    "talent community", "join our talent",
    "campus", "student program", "student intern",
    "diversity internship", "early career",
]

# Languages that are NOT English — if a job requires one of these,
# it likely needs native/fluent speakers from that language region.
NON_ENGLISH_LANGUAGES = [
    "vietnamese", "thai", "korean", "japanese", "chinese",
    "mandarin", "cantonese", "cyrillic", "russian", "polish",
    "czech", "hungarian", "romanian", "bulgarian", "croatian",
    "serbian", "slovak", "slovenian", "estonian", "latvian",
    "lithuanian", "turkish", "arabic", "hebrew", "hindi",
    "urdu", "bengali", "tamil", "telugu", "marathi",
    "malay", "indonesian", "filipino", "tagalog",
    "portuguese", "spanish", "french", "german", "italian",
    "dutch", "swedish", "norwegian", "danish", "finnish",
    "greek", "ukrainian", "kazakh",
]

# Pattern to detect bilingual requirements in titles.
# Examples: "Bilingual (Vietnamese/English)", "Spanish Speaking", "Fluent in French"
BILINGUAL_TITLE_RE = re.compile(
    r"bilingual\s*\(([^)]+)\)"
    r"|\bfluent\s+in\s+(\w+)"
    r"|\b(\w+)\s*\/\s*english"
    r"|\benglish\s*\/\s*(\w+)"
    r"|\bspeaking\s+(\w+)"
    r"|\b(\w+)\s+speaking"
    r"|\b(mandarin|cantonese|korean|japanese|vietnamese|thai|arabic|hebrew|polish|czech|hungarian|russian|turkish|french|german|spanish|portuguese|dutch|italian)\b",
    re.IGNORECASE,
)

# Timezone / business-hours restrictions buried in descriptions.
TIMEZONE_RESTRICTIONS = [
    "us hours", "us timezone", "eastern time", "pacific time",
    "central time", "mountain time", "eastern standard", "pacific standard",
    "north american hours", "us business hours",
    "must overlap", "overlap with us", "overlap with north american",
    "available during us", "available during north american",
    "working hours in the", "business hours in the us",
]

# "Preference" phrases that actually mean requirement.
PREFERENCE_PHRASES = [
    "preference towards candidates based in",
    "preference for candidates based in",
    "strong preference for candidates in",
    "prefer candidates located in",
    "preferably based in",
    "ideally based in",
    "we are hiring in",
    "we are only hiring in",
    "only hiring in",
]

# Words that mean "open to anyone, anywhere" -> eligible.
WORLDWIDE = [
    "anywhere", "worldwide", "global", "🌏", "remote", "remoto",
    "fully remote", "100% remote", "work from anywhere", "telecommute",
]

# Africa-related location signals -> eligible.
# Note: "emea" is NOT included here because EMEA = Europe, Middle East,
# Africa — most EMEA jobs are actually in Europe, not Africa. Only
# explicit Africa/East Africa/Rwanda/Kenya signals are trusted.
AFRICA = [
    "rwanda", "kigali", "kenya", "nairobi", "east africa", "africa",
    "middle east and africa",
]

# Regions in an eligible-country list that include Rwanda.
# Note: "emea" is excluded — most EMEA-listed jobs are in Europe.
RWANDA_OR_BROADER = [
    "rwanda", "kenya", "africa", "east africa", "middle east and africa",
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
_TITLE_REGION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in TITLE_REGION_CODES) + r")\b",
    re.IGNORECASE,
)
_GENERIC_TITLE_RE = re.compile(
    r"|".join(re.escape(w) for w in GENERIC_TITLES), re.IGNORECASE
)
_TIMEZONE_RE = re.compile(
    r"|".join(re.escape(w) for w in TIMEZONE_RESTRICTIONS), re.IGNORECASE
)
PREFERENCE_RE = re.compile(
    r"|".join(re.escape(w) for w in PREFERENCE_PHRASES), re.IGNORECASE
)


def _is_generic_title(title: str) -> bool:
    """Return True if the title is a generic posting, not a real job."""
    return bool(_GENERIC_TITLE_RE.search(title))


def _has_title_region_restriction(title: str) -> bool:
    """Return True if the title contains a region/country code."""
    return bool(_TITLE_REGION_RE.search(title))


def _has_description_restrictions(description: str) -> str | None:
    """Scan description for hidden timezone/region restrictions.

    Returns the first restriction found, or None if clean.
    """
    if not description:
        return None
    desc = description.lower()
    m = _TIMEZONE_RE.search(desc)
    if m:
        return f"timezone restriction: {m.group()}"
    m = PREFERENCE_RE.search(desc)
    if m:
        return f"region preference: {m.group()}"
    return None


def check_eligibility(job: Job) -> tuple[bool, str]:
    """Return (eligible, reason)."""

    # 0. Fast-reject: generic postings and title-based region restrictions.
    if _is_generic_title(job.title):
        return False, f"generic posting: {job.title[:50]}"
    if _has_title_region_restriction(job.title):
        return False, f"title has region restriction: {job.title[:50]}"

    # 0c. Fast-reject: bilingual jobs requiring non-English languages.
    # "Remote Bilingual Customer Support (Vietnamese/English)" -> reject
    # "Remote Bilingual Customer Support (English)" -> allow (English only)
    lang_match = BILINGUAL_TITLE_RE.search(job.title)
    if lang_match:
        # Extract all captured groups
        groups = [g for g in lang_match.groups() if g]
        for lang in groups:
            lang_lower = lang.lower().strip()
            # Check if it's a non-English language
            if lang_lower in NON_ENGLISH_LANGUAGES or any(le in lang_lower for le in NON_ENGLISH_LANGUAGES):
                return False, f"requires non-English language: {lang}"
            # Check if it's a slash pair like "Vietnamese/English"
            if "/" in lang:
                parts = [p.strip().lower() for p in lang.split("/")]
                non_eng = [p for p in parts if p != "english" and p in NON_ENGLISH_LANGUAGES]
                if non_eng:
                    return False, f"requires non-English language: {', '.join(non_eng)}"

    # 0b. Fast-reject: description-based timezone/region restrictions.
    desc_reject = _has_description_restrictions(job.description)
    if desc_reject:
        return False, desc_reject

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

    # Special case: standalone "EMEA" means open to EMEA (includes Africa),
    # but "Dublin, Ireland, EMEA" means the job is in Dublin.
    if _is_emea_only_location(loc):
        return True, f"EMEA (open to Africa): {loc[:60]}"

    # ATS "Remote" jobs: if the ORIGINAL location started with "Remote"
    # (e.g. "Remote - US", "Remote, San Francisco"), the job IS remote
    # even though it mentions a region. Many companies post "Remote - US"
    # but actually hire globally. Treat as eligible if the remaining text
    # is only a country/region code (not a specific city).
    loc_lower = (job.location or "").lower().strip()
    if loc_lower.startswith("remote"):
        # "Remote - US" -> remainder is "- us" or "us" -> eligible (country, not city)
        # "Remote, San Francisco" -> remainder is "san francisco" -> not eligible
        # "Remote - US, Select States" -> still too restricted
        stripped_remainder = remainder.lstrip("- ").strip()
        # Check if remainder is just a country name (not a specific city)
        is_country = any(c in stripped_remainder for c in [
            "us", "usa", "united states", "canada", "uk", "united kingdom",
            "europe", "emea", "apac", "latam", "americas",
        ])
        is_city = any(city in stripped_remainder for city in [
            "san francisco", "new york", "london", "berlin", "paris",
            "chicago", "los angeles", "seattle", "boston", "austin",
            "cardiff", "amsterdam", "dublin", "toronto", "sydney",
            "melbourne", "singapore", "tokyo", "bangalore", "mumbai",
            "bay area", "select states", "specific states",
        ])
        if is_city:
            return False, f"restricted location: {loc[:60]}"
        if is_country:
            return True, f"remote (country-level, likely global): {loc[:60]}"
        # Other remote-prefixed locations
        return True, f"remote (prefixed): {loc[:60]}"

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
