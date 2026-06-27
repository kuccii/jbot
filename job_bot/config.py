import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "opencode"
    model: str = "deepseek-v4-flash-free"
    embedding_model: str = "nomic-embed-text"
    temperature: float = 0.3
    gemini_api_key: str = ""
    nim_api_key: str = ""
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/zen/v1"
    ollama_base_url: str = "http://localhost:11434"


class DiscoveryConfig(BaseModel):
    interval_hours: int = 24
    sources: dict[str, bool] = Field(default_factory=lambda: {
        "google_search": True, "linkedin": True, "indeed": False,
        "ycombinator": True, "grants": True,
        "accelerators": True, "fellowships": True,
        "hackathons": True, "african_jobs": True, "twitter": False,
        "company_pages": True,
    })
    companies: list[str] = Field(default_factory=list)
    serper_api_key: str = ""
    grants_keywords: list[str] = Field(default_factory=list)
    sources_path: str = "data/sources.yaml"

    def __init__(self, **data):
        # Ensure all known source keys exist by merging YAML data with defaults
        defaults = {
            "google_search": True, "linkedin": True, "indeed": False,
            "ycombinator": True, "grants": True,
            "accelerators": True, "fellowships": True,
            "hackathons": True, "african_jobs": True, "twitter": False,
            "company_pages": True,
        }
        if "sources" in data and isinstance(data["sources"], dict):
            merged = defaults.copy()
            merged.update(data["sources"])
            data["sources"] = merged
        super().__init__(**data)


class ApplicationConfig(BaseModel):
    human_approval: bool = True
    max_applications_per_run: int = 5
    save_drafts: bool = True
    headless: bool = True


class WhatsAppConfig(BaseModel):
    enabled: bool = False
    phone_number_id: str = ""
    token: str = ""
    recipient: str = ""


class NotificationsConfig(BaseModel):
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)


class DatabaseConfig(BaseModel):
    path: str = "data/job_bot.db"
    vector_path: str = "data/vectors"


class ProfileConfig(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    cv_path: str = ""
    skills: list[str] = Field(default_factory=list)


class Config(BaseModel):
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    application: ApplicationConfig = Field(default_factory=ApplicationConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)


def load_config(config_path: str | None = None) -> Config:
    load_dotenv()
    path = Path(config_path) if config_path else (Path.cwd() / "config.yaml")
    if not path.exists():
        path = Path(__file__).parent / "config_default.yaml"
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Config file not found: {path}", file=sys.stderr)
        data = {}
    except yaml.YAMLError as e:
        print(f"Error parsing config file {path}: {e}", file=sys.stderr)
        data = {}
    if data is None:
        data = {}
    data = _inject_env_vars(data)
    return Config(**data)


def _inject_env_vars(data: dict) -> dict:
    mapping = {
        ("discovery", "serper_api_key"): "SERPER_API_KEY",
        ("notifications", "whatsapp", "phone_number_id"): "WHATSAPP_PHONE_NUMBER_ID",
        ("notifications", "whatsapp", "token"): "WHATSAPP_TOKEN",
        ("notifications", "whatsapp", "recipient"): "WHATSAPP_RECIPIENT",
    }
    for keys, env_var in mapping.items():
        val = os.getenv(env_var)
        if val:
            target = data
            for key in keys[:-1]:
                target = target.setdefault(key, {})
            target[keys[-1]] = val
    return data
