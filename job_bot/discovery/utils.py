"""
Utility functions for opportunity discovery — deadline parsing and expiry checks.
"""

import re
from datetime import datetime, timezone


# ── Month name helpers ───────────────────────────────────────────────────────

_MONTH_NAMES = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)

_MONTH_MAP: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_month(month_str: str) -> int | None:
    """Parse a month name (full or abbreviated) into its numeric value."""
    key = month_str.strip()[:3].lower()
    return _MONTH_MAP.get(key)


# ── Deadline-aware date regexes ──────────────────────────────────────────────
#
# All patterns are case-insensitive and capture (month, day, year) so the
# caller can build a datetime.  Two families:
#
#   A) "Deadline: June 30, 2026"  — keyword first, then month-name date
#   B) "Apply by 30-Jun-2026"     — keyword first, then day-first date
#   C) "by 28 June 2026"          — short keyword "by" + day-first date

_DEADLINE_KEYWORDS_A = r"(?:deadline|application\s+deadline|closing\s+date)"
_PATTERN_A = re.compile(
    rf"({_DEADLINE_KEYWORDS_A})\s*:?\s*"
    rf"({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.IGNORECASE,
)

_DEADLINE_KEYWORDS_B = r"(?:apply\s+by|closes?|due\s+date|applications?\s+close)"
_PATTERN_B = re.compile(
    rf"({_DEADLINE_KEYWORDS_B})\s*:?\s*"
    rf"(\d{{1,2}})[-/\s]+({_MONTH_NAMES})[-/\s]+(\d{{4}})",
    re.IGNORECASE,
)

_PATTERN_C = re.compile(
    rf"\b(by)\s+(\d{{1,2}})[-/\s]+({_MONTH_NAMES})[-/\s]+(\d{{4}})",
    re.IGNORECASE,
)


def extract_deadline(text: str) -> datetime | None:
    """Parse a deadline/application-close date from *text*.

    Supports the following formats near deadline-related keywords:

    * ``Deadline: June 30, 2026``
    * ``Apply by 30-Jun-2026``
    * ``Application Deadline: July 2nd, 2026``
    * ``Deadline: 31-Aug-2026``
    * ``Closes: 15 July 2026``
    * ``by 28 June 2026``
    * ``Applications close 30 June 2026``

    Returns a timezone-aware :class:`~datetime.datetime` (UTC) or *None*.
    """
    if not text:
        return None

    # ── Pattern A: keyword + "Month DD, YYYY" ──────────────────────────────
    m = _PATTERN_A.search(text)
    if m:
        month = _parse_month(m.group(2))
        day = int(m.group(3))
        year = int(m.group(4))
        if month:
            return _make_aware(year, month, day)

    # ── Pattern B: keyword + "DD-Mon-YYYY" or "DD Mon YYYY" ───────────────
    m = _PATTERN_B.search(text)
    if m:
        day = int(m.group(2))
        month = _parse_month(m.group(3))
        year = int(m.group(4))
        if month:
            return _make_aware(year, month, day)

    # ── Pattern C: "by DD Mon YYYY" ───────────────────────────────────────
    m = _PATTERN_C.search(text)
    if m:
        day = int(m.group(2))
        month = _parse_month(m.group(3))
        year = int(m.group(4))
        if month:
            return _make_aware(year, month, day)

    return None


def _make_aware(year: int, month: int, day: int) -> datetime:
    """Return a timezone-aware UTC datetime representing 23:59:59 on *day*.

    Using the end of the day gives applicants the full final day to apply.
    """
    return datetime(year, month, day, 23, 59, 59, tzinfo=timezone.utc)


def is_expired(deadline: datetime | None) -> bool:
    """Return ``True`` when *deadline* is not ``None`` and is in the past.

    Always uses timezone-aware comparisons (converts naive datetimes to UTC).
    """
    if deadline is None:
        return False
    now = datetime.now(timezone.utc)
    # Make the deadline timezone-aware if it isn't already
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return deadline < now


# ── Rwanda eligibility filter for all opportunities ──────────────────────────

_LOCATIONS_EXCLUDING_RWANDA = [
    "us", "usa", "united states", "uk", "united kingdom", "canada",
    "australia", "new zealand", "singapore", "japan", "china",
    "germany", "france", "spain", "italy", "netherlands", "switzerland",
    "sweden", "norway", "denmark", "finland", "belgium", "austria",
    "ireland", "poland", "portugal",
    # Additional non-Rwanda countries
    "south korea", "taiwan", "india", "indonesia", "malaysia",
    "philippines", "thailand", "vietnam", "israel", "uae",
    "united arab emirates", "qatar", "saudi arabia",
    "brazil", "argentina", "chile", "colombia", "mexico",
]

_VISA_BLOCK_KEYWORDS = [
    "us work authorization", "eligible to work in the", "must be based in",
    "must be located in", "no visa sponsorship", "cannot sponsor",
    "us citizen", "us permanent resident", "green card",
    "must have work authorization", "must be eligible to work",
    "within commuting distance", "eu work permit", "uk right to work",
    "we are unable to sponsor", "not able to sponsor",
    "must already have work authorization",
    "must be legally authorized", "employment eligibility",
]

_GLOBAL_HIRE_KEYWORDS = [
    "anywhere in the world", "work from anywhere", "global", "worldwide",
    "remote-first", "remote first", "open to applicants from anywhere",
    "fully remote", "100% remote",
]

_POSITIVE_LOCATIONS = ["africa", "rwanda", "east africa", "global", "worldwide", "anywhere", "emea"]

# ── Title-based location pattern extraction ──────────────────────────────────
# Many ATS entries have location only in the title, e.g.:
#   "Engineer - San Francisco"     → dash suffix
#   "Manager (London)"             → paren suffix
#   "Lead, UK"                     → comma suffix
#   "AE - DACH Market"             → region in parens
#   "SA - Saudi Arabia"            → country in parens

_TITLE_CITY_SUFFIX_RE = re.compile(
    r"""
    [,\s–—-]\s*                    # separator: comma, dash, en-dash, em-dash
    (?:(
        (?:                         # city / country
            san\s+francisco|new\s+york|los\s+angeles|washington\s+dc|
            chicago|boston|denver|seattle|portland|austin|dallas|
            houston|phoenix|miami|atlanta|detroit|minneapolis|
            philadelphia|san\s+diego|sanjose|palo\s+alto|mountain\s+view|
            london|paris|berlin|dublin|madrid|barcelona|munich|
            hamburg|cologne|frankfurt|stuttgart|dusseldorf|
            amsterdam|brussels|vienna|prague|warsaw|copenhagen|
            stockholm|oslo|helsinki|lisbon|zurich|geneva|
            rome|milan|turkey|istanbul|athens|
            beijing|shanghai|hong\s+kong|tokyo|seoul|mumbai|
            bangalore|singapore|sydney|melbourne|auckland|
            toronto|vancouver|montreal|mexico\s+city|sao\s+paulo|
            buenos\s+aires|bogota|santiago|lima|
            cairo|nairobi|lagos|cape\s+town|johannesburg|
            casablanca|tunis|accra|dakar|addis\s+ababa|kigali|
            dubai|doha|riyadh|jeddah|tel\s+aviv|kuwait|
        )|
        (?:                         # region / country
            uk|u\.k\.|u\.s\.|usa|us|
            emea|latam|apac|dach|benelux|nordic|iberia|
            uk\s*&\s*ireland|uk\s*&\s*europe|
            united\s+states|united\s+kingdom|
            australia|new\s+zealand|canada|japan|china|india|
            singapore|hong\s+kong|south\s+korea|taiwan|
            germany|france|spain|italy|netherlands|switzerland|
            sweden|norway|denmark|finland|belgium|austria|
            ireland|poland|portugal|greece|turkey|
            saudi\s+arabia|uae|qatar|israel|
            brazil|mexico|argentina|chile|colombia|
            south\s+africa|nigeria|kenya|ghana|morocco|egypt|
        )
    )\s*(?:market|region|area)?\s*
    (?:\([^)]*\))?                  # optional trailing paren
    )$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# US state abbreviations and full names for title matching
_US_STATES = [
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    # full names
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming",
]

# Cities that strongly imply US/EU location and are unlikely to offer visa sponsorship
_CITIES_EXCLUDING_RWANDA = [
    "san francisco", "new york", "los angeles", "chicago", "boston",
    "denver", "seattle", "portland", "austin", "dallas", "houston",
    "miami", "atlanta", "phoenix", "detroit", "san diego",
    "london", "paris", "berlin", "dublin", "madrid", "barcelona",
    "munich", "amsterdam", "brussels", "stockholm", "copenhagen",
    "oslo", "helsinki", "zurich", "geneva", "rome", "milan",
    "beijing", "shanghai", "hong kong", "tokyo", "seoul", "singapore",
    "sydney", "melbourne", "toronto", "vancouver", "montreal",
    "mexico city", "sao paulo", "buenos aires",
    "washington dc", "washington d.c.",
]

_REGIONS_EXCLUDING_RWANDA = [
    "dach", "latam", "apac", "nordic", "iberia", "benelux",
]

_POSITIVE_TITLE_MARKERS = [
    "remote", "anywhere", "global", "worldwide", "africa",
    "east africa", "emea",
]


def _extract_title_location(title: str) -> str | None:
    """Extract location suffix from a job title.

    Handles patterns like:
      "Engineer - San Francisco"     → "san francisco"
      "Manager (London)"             → "london"
      "Lead, UK"                     → "uk"
      "AE (DACH Market)"             → "dach market"
    """
    t = title.strip()
    # Pattern 1: "... (Location)"  — parenthetical suffix
    m = re.search(r"\(([^)]+)\)\s*$", t)
    if m:
        loc = m.group(1).strip().lower()
        # Clean up common suffixes
        loc = re.sub(r"\s+(market|region|area|based)\s*$", "", loc)
        loc = loc.strip()
        if loc and len(loc) > 1:
            return loc

    # Pattern 2: "... - Location" or "... – Location" — dash suffix
    m = re.search(r"[,\s–—-–—]\s*([A-Za-z].*?)\s*$", t)
    if m:
        loc = m.group(1).strip().lower()
        # Remove trailing parenthetical qualifiers
        loc = re.sub(r"\s*\([^)]*\)\s*$", "", loc).strip()
        # Clean up common words
        loc = re.sub(r"\s+(market|region|area|based)\s*$", "", loc)
        loc = loc.strip()
        if loc and len(loc) > 1 and loc not in ("", "remote", "hybrid", "on-site", "onsite"):
            return loc

    # Pattern 3: "... in Location" — "in" suffix
    m = re.search(r"\bin\s+([A-Za-z].*?)\s*$", t)
    if m:
        loc = m.group(1).strip().lower()
        loc = re.sub(r"\s*\([^)]*\)\s*$", "", loc).strip()
        if loc and len(loc) > 1:
            return loc

    return None


def _title_location_is_excluded(title_lower: str) -> bool:
    """Check if the title contains a location that makes it ineligible."""

    # Fast check: known excluded city/region in title
    for city in _CITIES_EXCLUDING_RWANDA:
        if city in title_lower:
            return True

    # Fast check: known excluded regions (DACH, LATAM, APAC, etc.)
    for region in _REGIONS_EXCLUDING_RWANDA:
        if re.search(r"(?:^|[,\s(\-–—])" + re.escape(region) + r"(?:[,\s)\-–—]|$)", title_lower):
            return True

    # Fast check: US state in title (word-boundary matched)
    for state in _US_STATES:
        if re.search(r"(?:^|[,\s(\-–—])" + re.escape(state) + r"(?:[,\s)\-–—]|$)", title_lower):
            return True

    # Check for country/region names directly in title (word-boundary matched)
    for excl in _LOCATIONS_EXCLUDING_RWANDA:
        if len(excl) > 2:  # skip short entries like "us", "uk" that might match embedded
            if re.search(r"(?:^|[,\s(\-–—])" + re.escape(excl) + r"(?:[,\s)\-–—]|$)", title_lower):
                return True

    # Check for "US-based", "US only", "US remote", etc.
    # Match "us" as a word with trailing separator, avoiding false positives
    # like "focus", "museum", "bus", "just", "plus"
    if re.search(r"(?:^|[,\s(\-–—])us(?:[\s\-–—,.)]|$)", title_lower) and not re.search(r"\b(?:us\s*dollar|usd|united\s+states\s+(of\s+)?africa)", title_lower):
        return True
    # Check for "u.s." pattern
    if re.search(r"\bu\.s\.", title_lower):
        return True

    # Extract structured location from title suffix (parens, dash, comma)
    extracted = _extract_title_location(title_lower)
    if extracted:
        # Check if extracted location is an exact match for excluded countries
        if extracted in [c.lower() for c in _LOCATIONS_EXCLUDING_RWANDA]:
            return True
        # Check if it contains an excluded country/region name
        for excl in _LOCATIONS_EXCLUDING_RWANDA:
            if excl in extracted:
                return True
        # Check if extracted location is a city
        for city in _CITIES_EXCLUDING_RWANDA:
            if city in extracted or extracted in city:
                return True

    return False


def is_rwanda_eligible(title: str, company: str, description: str | None, location: str | None, remote: str | None) -> bool:
    """Check whether a person from Rwanda is likely eligible for this opportunity."""
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    loc_lower = (location or "").lower()
    remote_lower = (remote or "").lower()
    company_lower = (company or "").lower()

    # Fast positive — explicitly global/anywhere/africa
    if any(kw in desc_lower for kw in ["anywhere in the world", "work from anywhere", "open to applicants from anywhere"]):
        return True
    if any(kw in loc_lower for kw in _POSITIVE_LOCATIONS):
        return True
    if remote_lower in ("worldwide", "global", "anywhere"):
        return True
    # Check title for positive location markers
    for marker in _POSITIVE_TITLE_MARKERS:
        if marker in title_lower:
            # Only if not also location-locked (e.g., "Remote - US" should still fail)
            if not re.search(r"remote[\s\-–—]+(us|usa|uk|canada|eu|europe|australia)", title_lower):
                return True

    # Fast negative — title-based location exclusion
    if _title_location_is_excluded(title_lower):
        return False

    # Fast negative — location-based exclusion (if location field is populated)
    if loc_lower:
        parts = loc_lower.replace("(", "").replace(")", "").replace(";", ",").replace("/", ",").split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part in ("remote", "fully remote", "100% remote"):
                continue
            if any(country in part for country in _LOCATIONS_EXCLUDING_RWANDA):
                return False
            if any(state in part for state in ("ny", "ca", "tx", "il", "fl", "wa", "ma", "or", "co", "dc")):
                return False

    # Fast negative — visa/authorization blocks (skip if followed by positive locations)
    if "must be located in" in desc_lower:
        after = desc_lower.split("must be located in", 1)[1]
        if not any(pos in after for pos in ("africa", "rwanda", "east africa", "global", "anywhere", "worldwide")):
            return False
    if any(kw in desc_lower for kw in [k for k in _VISA_BLOCK_KEYWORDS if k != "must be located in"]):
        return False

    # Remote with no geographic restriction → eligible
    if "remote" in remote_lower and not any(restriction in desc_lower for restriction in ["remote - us", "remote us", "remote in the us", "remote in us", "remote - uk", "remote uk", "remote - eu", "remote eu"]):
        return True
    if "remote" in title_lower and "remote" not in loc_lower:
        # Double-check it's not "Remote - US" style
        if not re.search(r"remote[\s\-–—]+(us|usa|uk|canada|eu|europe|australia)", title_lower):
            return True

    # Default: keep it (will be scored by AI)
    return True


# ── Geography filter for startup/grant opportunities ──────────────────────────

_OTHER_AFRICAN_COUNTRIES = [
    "ghana", "nigeria", "kenya", "south africa", "uganda", "ethiopia",
    "egypt", "morocco", "senegal", "ivory coast", "côte d'ivoire",
    "cameroon", "zambia", "zimbabwe", "mozambique", "angola",
    "botswana", "malawi", "mali", "burkina faso", "niger", "benin",
    "togo", "congo", "liberia", "sierra leone", "south sudan",
    "mauritania", "chad", "gabon", "namibia", "madagascar",
    "swaziland", "eswatini", "lesotho", "eritrea", "central african republic",
    "the gambia", "gambia", "mauritius", "seychelles", "cape verde",
    "comoros", "djibouti", "equatorial guinea", "guinea", "guinea-bissau",
    "sao tome", "somalia",
]


def is_rwanda_tanzania_eligible(title: str, snippet: str) -> bool:
    """Check startup/grant results are relevant to Rwanda or Tanzania.

    If the text explicitly mentions non-Rwanda/Tanzania African countries
    without also mentioning Rwanda or Tanzania, it is rejected.
    """
    text = (title + " " + snippet).lower()

    rwanda_tz = {"rwanda", "tanzania"}
    mentions_rwanda_tz = any(c in text for c in rwanda_tz)
    mentions_other = any(c in text for c in _OTHER_AFRICAN_COUNTRIES)

    if mentions_rwanda_tz:
        return True
    if mentions_other:
        return False
    if "east africa" in text:
        return True
    return True  # no country mentioned → general opportunity, keep it
