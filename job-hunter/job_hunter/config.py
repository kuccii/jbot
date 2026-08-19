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


# Companies whose ATS boards were verified live against public APIs.
# The eligibility filter still applies per-posting, so country-restricted
# roles are dropped automatically.
DEFAULT_ATS_COMPANIES: list[dict] = [
    # ── Greenhouse ─────────────────────────────────────────────────────────
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
    {"name": "Discord", "ats": "greenhouse", "slug": "discord"},
    {"name": "DataDog", "ats": "greenhouse", "slug": "datadog"},
    {"name": "Cloudflare", "ats": "greenhouse", "slug": "cloudflare"},
    {"name": "Postman", "ats": "greenhouse", "slug": "postman"},
    {"name": "Algolia", "ats": "greenhouse", "slug": "algolia"},
    {"name": "Buildkite", "ats": "greenhouse", "slug": "buildkite"},
    {"name": "Fivetran", "ats": "greenhouse", "slug": "fivetran"},
    {"name": "Wise", "ats": "greenhouse", "slug": "wise"},
    {"name": "HackerRank", "ats": "greenhouse", "slug": "hackerrank"},
    {"name": "Brex", "ats": "greenhouse", "slug": "brex"},
    {"name": "Coinbase", "ats": "greenhouse", "slug": "coinbase"},
    {"name": "Mercury", "ats": "greenhouse", "slug": "mercury"},
    {"name": "Duolingo", "ats": "greenhouse", "slug": "duolingo"},
    {"name": "Prisma", "ats": "greenhouse", "slug": "prisma"},
    {"name": "PlanetScale", "ats": "greenhouse", "slug": "planetscale"},
    {"name": "Netlify", "ats": "greenhouse", "slug": "netlify"},
    {"name": "Fastly", "ats": "greenhouse", "slug": "fastly"},
    {"name": "Elastic", "ats": "greenhouse", "slug": "elastic"},
    {"name": "Twitch", "ats": "greenhouse", "slug": "twitch"},
    {"name": "Xometry", "ats": "greenhouse", "slug": "xometry"},
    {"name": "Checkr", "ats": "greenhouse", "slug": "checkr"},
    {"name": "N26", "ats": "greenhouse", "slug": "n26"},
    {"name": "SumUp", "ats": "greenhouse", "slug": "sumup"},
    {"name": "Storyblok", "ats": "greenhouse", "slug": "storyblok"},
    {"name": "Calendly", "ats": "greenhouse", "slug": "calendly"},
    {"name": "Dialpad", "ats": "greenhouse", "slug": "dialpad"},
    {"name": "Gusto", "ats": "greenhouse", "slug": "gusto"},
    {"name": "HubSpot", "ats": "greenhouse", "slug": "hubspot"},
    {"name": "New Relic", "ats": "greenhouse", "slug": "newrelic"},
    {"name": "Okta", "ats": "greenhouse", "slug": "okta"},
    {"name": "PandaDoc", "ats": "greenhouse", "slug": "pandadoc"},
    {"name": "Robinhood", "ats": "greenhouse", "slug": "robinhood"},
    {"name": "Samsara", "ats": "greenhouse", "slug": "samsara"},
    {"name": "Calm", "ats": "greenhouse", "slug": "calm"},
    {"name": "Lattice", "ats": "greenhouse", "slug": "lattice"},
    {"name": "Squarespace", "ats": "greenhouse", "slug": "squarespace"},
    {"name": "Vekada", "ats": "greenhouse", "slug": "verkada"},
    {"name": "Thinkific", "ats": "greenhouse", "slug": "thinkific"},
    {"name": "Upwork", "ats": "greenhouse", "slug": "upwork"},
    {"name": "ZipRecruiter", "ats": "greenhouse", "slug": "ziprecruiter"},
    {"name": "Rubrik", "ats": "greenhouse", "slug": "rubrik"},
    {"name": "Marqeta", "ats": "greenhouse", "slug": "marqeta"},
    # ── Ashby ──────────────────────────────────────────────────────────────
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
    {"name": "Ramp", "ats": "ashby", "slug": "ramp"},
    {"name": "Replit", "ats": "ashby", "slug": "replit"},
    {"name": "Vercel (Ashby)", "ats": "ashby", "slug": "vercel"},
    {"name": "Sanity", "ats": "ashby", "slug": "sanity"},
    {"name": "Supabase", "ats": "ashby", "slug": "supabase"},
    {"name": "Railway", "ats": "ashby", "slug": "railway"},
    {"name": "Render", "ats": "ashby", "slug": "render"},
    {"name": "Runway", "ats": "ashby", "slug": "runway"},
    {"name": "Chromatic", "ats": "ashby", "slug": "chromatic"},
    {"name": "GitBook", "ats": "ashby", "slug": "gitbook"},
    {"name": "Prefect", "ats": "ashby", "slug": "prefect"},
    {"name": "Airbyte", "ats": "ashby", "slug": "airbyte"},
    {"name": "Help Scout", "ats": "ashby", "slug": "helpscout"},
    {"name": "Plaid", "ats": "ashby", "slug": "plaid"},
    {"name": "Snyk", "ats": "ashby", "slug": "snyk"},
    {"name": "Windfall", "ats": "ashby", "slug": "windfall"},
    {"name": "Marqeta", "ats": "ashby", "slug": "marqeta"},
    {"name": "Vekada", "ats": "ashby", "slug": "verkada"},
    {"name": "Thinkific", "ats": "ashby", "slug": "thinkific"},
    {"name": "Neon", "ats": "ashby", "slug": "neon"},
    # ── SmartRecruiters ────────────────────────────────────────────────────
    {"name": "Canva", "ats": "smartrecruiters", "slug": "canva"},
    {"name": "Spotify", "ats": "smartrecruiters", "slug": "spotify"},
    {"name": "Adobe", "ats": "smartrecruiters", "slug": "adobe"},
    {"name": "Shopify", "ats": "smartrecruiters", "slug": "shopify"},
    {"name": "SAP", "ats": "smartrecruiters", "slug": "sap"},
    {"name": "Salesforce", "ats": "smartrecruiters", "slug": "salesforce"},
    {"name": "Oracle", "ats": "smartrecruiters", "slug": "oracle"},
    {"name": "IBM", "ats": "smartrecruiters", "slug": "ibm"},
    {"name": "Cisco", "ats": "smartrecruiters", "slug": "cisco"},
    {"name": "VMware", "ats": "smartrecruiters", "slug": "vmware"},
    {"name": "ServiceNow", "ats": "smartrecruiters", "slug": "servicenow"},
    {"name": "Workday", "ats": "smartrecruiters", "slug": "workday"},
    {"name": "Atlassian", "ats": "smartrecruiters", "slug": "atlassian"},
    {"name": "Splunk", "ats": "smartrecruiters", "slug": "splunk"},
    {"name": "Palo Alto Networks", "ats": "smartrecruiters", "slug": "paloalto"},
    {"name": "CrowdStrike", "ats": "smartrecruiters", "slug": "crowdstrike"},
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
        "arc": True,
        "weworkremotely": False,  # unreliable (403s from datacenter IPs)
    })
    keywords: list[str] = Field(default_factory=list)
    ats_companies: list[ATSCompanyConfig] = Field(
        default_factory=lambda: [ATSCompanyConfig(**c) for c in DEFAULT_ATS_COMPANIES]
    )
    database: str = "data/jobs.db"
    max_jobs_per_board: int = 200


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
