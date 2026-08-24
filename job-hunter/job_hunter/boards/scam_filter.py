"""Scam and unreliable platform filter.

Certain job/gig platforms are known to be unreliable, pay poorly, or are
outright scams. This module provides:

1. ``UNRELIABLE_COMPANIES`` — company names to reject
2. ``UNRELIABLE_TITLE_PATTERNS`` — title patterns to reject
3. ``is_unreliable(title, company, description)`` — check if a job is suspect

Sources:
- r/beermoney, r/workonline, r/mturk community reports
- Trustpilot reviews
- Known scam patterns (upfront fees, guaranteed income, etc.)
"""

from __future__ import annotations

import re

# Companies/platforms with poor payment records or scam reports.
# These are rejected outright — no need to store them.
UNRELIABLE_COMPANIES: set[str] = {
    # Known scam platforms
    "clickworker",  # Very low pay, inconsistent
    "microworkers",  # Pennies per task
    "swagbucks",  # Rewards site, not real work
    "inboxdollars",  # Rewards site
    "featurepoints",  # Rewards site
    "appen",  # Pay rates declined significantly, unreliable payments

    # Pay-to-work scams
    "smartworker",  # Requires upfront fee
    "workersonboard",  # Requires upfront fee

    # Ghost companies (post jobs but never hire)
    "talentify",  # Automated, never responds
    "hirevue",  # AI interview bots, rarely leads to jobs
}

# Title patterns indicating scams or low-quality work.
UNRELIABLE_TITLE_PATTERNS: list[str] = [
    # Upfront fee scams
    r"pay\s+(?:to|for)\s+work",
    r"registration\s+fee",
    r"startup\s+fee",
    r"training\s+fee\s+required",

    # Guaranteed income scams
    r"guaranteed\s+(?:income|earnings|money)",
    r"earn\s+\$?\d+[kK]\s+(?:per|a)\s+(?:day|week|month)",
    r"make\s+money\s+(?:fast|online|easy)",
    r"work\s+from\s+home\s+(?:scam|legit|real)",

    # MLM / Pyramid schemes
    r"multi[- ]?level\s+marketing",
    r"mlm",
    r"network\s+marketing",
    r"pyramid\s+(?:scheme|structure)",
    r"recruit\s+(?:others|people|team)",

    # Low-quality micro-tasks
    r"micro[- ]?task",
    r"captcha\s+(?:entry|solving|typing)",
    r"data\s+entry\s+(?:clerk|operator)\s+(?:wanted|needed)",
    r"typing\s+(?:job|work|assignment)",

    # Suspicious vague promises
    r"no\s+experience\s+needed.*(?:high|unlimited)\s+pay",
    r"work\s+at\s+home.*(?:mom|parent|student)",
    r"financial\s+freedom",
]

# Compile patterns for efficiency
_UNRELIABLE_TITLE_RE = re.compile(
    "|".join(UNRELIABLE_TITLE_PATTERNS), re.IGNORECASE
)


def is_unreliable(
    title: str = "",
    company: str = "",
    description: str = "",
) -> tuple[bool, str]:
    """Check if a job is from an unreliable source.

    Returns (is_unreliable, reason).
    """
    company_lower = company.strip().lower()
    title_lower = title.strip().lower()

    # Check company name
    for bad in UNRELIABLE_COMPANIES:
        if bad in company_lower:
            return True, f"unreliable platform: {company}"

    # Check title patterns
    m = _UNRELIABLE_TITLE_RE.search(title)
    if m:
        return True, f"suspicious title pattern: {m.group()}"

    # Check description for scam signals
    desc_lower = description.lower()
    scam_signals = [
        "upfront fee",
        "pay to start",
        "registration required",
        "guaranteed income",
        "no experience high pay",
        "earn money fast",
        "click here to earn",
    ]
    for signal in scam_signals:
        if signal in desc_lower:
            return True, f"scam signal in description: {signal}"

    return False, ""
