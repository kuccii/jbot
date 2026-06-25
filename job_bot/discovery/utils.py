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
