from __future__ import annotations
import re
from pathlib import Path
import yaml

# The only hand-maintained bridge: CV skill phrases -> job-text tokens.
# Multi-word CV headings do not match job postings directly, so each expands
# to the tokens scoring actually looks for. Extend when cv.md gains a skill.
SKILL_EXPANSIONS: dict[str, list[str]] = {
    "cloud systems": ["cloud", "aws", "azure", "gcp"],
    "ai & automation": ["ai", "automation", "llm", "machine learning", "prompt"],
    "mobile & web development": ["mobile", "web", "react", "javascript", "python", "api"],
    "databases": ["sql", "postgresql", "database"],
    "devops tools": ["devops", "docker", "kubernetes", "ci/cd"],
    "product planning & roadmapping": ["product management", "product manager", "roadmap"],
    "task prioritization & resource allocation": ["prioritization", "resource planning"],
    "kpi tracking & performance analysis": ["kpi", "analytics", "metrics"],
    "agile & scrum methodologies": ["agile", "scrum"],
    "project management": ["project management", "project manager"],
}

_PROFILE_BLOCK_RE = re.compile(r"(?ms)^profile:.*?(?=^\S|\Z)")

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def derive_skills(cv_text: str, target_roles: list[str]) -> list[str]:
    """Expand CV skill phrases + target roles into scoring tokens."""
    tokens: set[str] = set()
    for line in cv_text.splitlines():
        for phrase in line.split(","):
            key = _norm(phrase)
            if key in SKILL_EXPANSIONS:
                tokens.update(SKILL_EXPANSIONS[key])
    for role in target_roles:
        tokens.add(_norm(role))
    return sorted(t for t in tokens if t)

def build_profile(profile_yml: dict, cv_text: str) -> dict:
    return {
        "name": profile_yml.get("name", ""),
        "email": profile_yml.get("email", ""),
        "location": profile_yml.get("location", "Rwanda"),
        "seniority": "mid",
        "skills": derive_skills(cv_text, profile_yml.get("target_roles", [])),
    }

def replace_profile_block(config_text: str, profile: dict) -> str:
    """Replace the top-level ``profile:`` block, preserving everything else."""
    body = yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)
    block = "profile:\n" + "".join("  " + ln + "\n" for ln in body.splitlines())
    if _PROFILE_BLOCK_RE.search(config_text):
        return _PROFILE_BLOCK_RE.sub(block, config_text, count=1)
    sep = "" if config_text.endswith("\n") else "\n"
    return config_text + sep + block
