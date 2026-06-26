from pathlib import Path

import yaml
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    enabled: bool = True
    type: str = "serper"
    queries: list[str] = []
    targets: list[str] = []
    label: str = ""


class SourcesConfig(BaseModel):
    providers: dict[str, ProviderConfig] = {}


def load_sources(path: str | Path) -> SourcesConfig:
    path = Path(path)
    if not path.exists():
        return SourcesConfig()
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return SourcesConfig(**data)
