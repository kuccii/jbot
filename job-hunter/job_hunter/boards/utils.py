"""Shared utilities for board scrapers.

Centralizes HTML stripping and remote/worldwide location detection so
individual boards don't duplicate this logic.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

def strip_html(text: str | None, max_len: int = 2000) -> str:
    """Strip HTML tags and collapse whitespace, truncating to *max_len* chars."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return " ".join(clean.split())[:max_len]


# ---------------------------------------------------------------------------
# Remote / worldwide location detection
# ---------------------------------------------------------------------------

# Location values (lowercased) that mean "open to anyone, anywhere".
WORLDWIDE: set[str] = {
    "anywhere", "worldwide", "global", "any country", "all countries",
    "🌏", "international", "emea", "middle east and africa",
    "remote", "remoto",
}

# Patterns that indicate a remote/worldwide role in a location string.
_WORLDWIDE_RE = re.compile(
    r"🌏|worldwide|anywhere|global|100% remote|fully remote|"
    r"work from anywhere|remote-first|remoto|telecommute",
    re.IGNORECASE,
)


def is_worldwide(location: str) -> bool:
    """Return True if *location* indicates the role is open worldwide."""
    low = location.strip().lower()
    if low in WORLDWIDE:
        return True
    return bool(_WORLDWIDE_RE.search(low))


def remote_status(location: str) -> str:
    """Return ``"Remote"`` if the location signals worldwide, else ``""``."""
    return "Remote" if is_worldwide(location) else ""
