"""Configuration loading for job-hunter."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    name: str = ""
    email: str = ""
    location: str = "Kigali, Rwanda"
    skills: list[str] = Field(default_factory=list)


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
        "weworkremotely": False,  # unreliable (403s from datacenter IPs)
    })
    keywords: list[str] = Field(default_factory=list)
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
