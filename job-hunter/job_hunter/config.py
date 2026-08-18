"""Configuration loading for job-hunter."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    name: str = ""
    email: str = ""
    location: str = "Kigali, Rwanda"
    skills: list[str] = Field(default_factory=list)


class ATSCompanyConfig(BaseModel):
    name: str
    ats: str  # "greenhouse" | "ashby" | "smartrecruiters"
    slug: str


# Companies whose ATS boards were verified live (26/28 resolve to real
# public APIs). The eligibility filter still applies per-posting, so
# country-restricted roles are dropped automatically.
DEFAULT_ATS_COMPANIES: list[dict] = [
    # Greenhouse
    {"name": "GitLab", "ats": "greenhouse", "slug": "gitlab"},
    {"name": "Stripe", "ats": "greenhouse", "slug": "stripe"},
    {"name": "Remote.com", "ats": "greenhouse", "slug": "remote"},
    {"name": "Anthropic", "ats": "greenhouse", "slug": "anthropic"},
    {"name": "Instacart", "ats": "greenhouse", "slug": "instacart"},
    {"name": "Monzo", "ats": "greenhouse", "slug": "monzo"},
    {"name": "Figma", "ats": "greenhouse", "slug": "figma"},
    {"name": "Dropbox", "ats": "greenhouse", "slug": "dropbox"},
    {"name": "Airtable", "ats": "greenhouse", "slug": "airtable"},
    {"name": "Vercel", "ats": "greenhouse", "slug": "vercel"},
    # Ashby
    {"name": "Deel", "ats": "ashby", "slug": "deel"},
    {"name": "OpenAI", "ats": "ashby", "slug": "openai"},
    {"name": "Zapier", "ats": "ashby", "slug": "zapier"},
    {"name": "Linear", "ats": "ashby", "slug": "linear"},
    {"name": "ElevenLabs", "ats": "ashby", "slug": "elevenlabs"},
    {"name": "Notion", "ats": "ashby", "slug": "notion"},
    {"name": "Resend", "ats": "ashby", "slug": "resend"},
    {"name": "Percona", "ats": "ashby", "slug": "percona"},
    {"name": "Cohere", "ats": "ashby", "slug": "cohere"},
    {"name": "ClickUp", "ats": "ashby", "slug": "clickup"},
    {"name": "1Password", "ats": "ashby", "slug": "1password"},
    {"name": "Sentry", "ats": "ashby", "slug": "sentry"},
    {"name": "PostHog", "ats": "ashby", "slug": "posthog"},
    # SmartRecruiters
    {"name": "Canva", "ats": "smartrecruiters", "slug": "canva"},
]

class Config(BaseModel):
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    boards: dict[str, bool] = Field(default_factory=lambda: {
        "remoteok": True,
        "remote4africa": True,
        "himalayas": True,
        "remotive": True,
        "persona": True,
        "workingnomads": True,
        "jobicy": True,
        "ats": True,
        "weworkremotely": False,  # unreliable (403s from datacenter IPs)
    })
    keywords: list[str] = Field(default_factory=list)
    ats_companies: list[ATSCompanyConfig] = Field(
        default_factory=lambda: [ATSCompanyConfig(**c) for c in DEFAULT_ATS_COMPANIES]
    )
    database: str = "data/jobs.db"
    max_jobs_per_board: int = 30


def load_config(config_path: str | None = None) -> Config:
    path = Path(config_path) if config_path else (Path.cwd() / "config.yaml")
    if not path.exists():
        path = Path(__file__).parent.parent / "config.yaml"
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    return Config(**data)
