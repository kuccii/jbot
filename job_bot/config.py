import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "llama3.1:8b"
    embedding_model: str = "nomic-embed-text"
    temperature: float = 0.3


class DiscoveryConfig(BaseModel):
    interval_hours: int = 24
    sources: dict[str, bool] = Field(default_factory=lambda: {
        "google_search": True, "linkedin": True, "indeed": False,
        "ycombinator": True, "grants": True,
    })
    companies: list[str] = Field(default_factory=list)
    serper_api_key: str = ""
    grants_keywords: list[str] = Field(default_factory=list)


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
