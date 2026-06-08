# Phase 1: Project Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up the Python project scaffold, configuration system, database models, CLI skeleton, and utility modules.

**Architecture:** Monolithic Python application with modular packages. This phase establishes the directory structure, config management (YAML + env vars), SQLite database via SQLAlchemy, Typer CLI, and shared utilities (logging, retry, encryption). All subsequent phases build on this foundation.

**Tech Stack:** Python 3.11+, SQLAlchemy, SQLite, Typer, structlog, pydantic, python-dotenv, APScheduler

---

### Task 1: Project Structure and Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `job_bot/__init__.py`
- Create: `job_bot/__main__.py`
- Create: `.env.example`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "job-bot"
version = "0.1.0"
description = "Automated job application discovery and submission bot"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0",
    "typer>=0.12",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "structlog>=24.0",
    "apscheduler>=3.10",
    "cryptography>=42.0",
    "pydantic>=2.0",
    "httpx>=0.27",
    "playwright>=1.45",
    "chromadb>=0.5",
    "sentence-transformers>=3.0",
]

[project.scripts]
job-bot = "job_bot.cli.commands:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["job_bot*"]
```

- [ ] **Step 2: Create `.env.example`**

```env
# --- LLM Providers ---
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_API_KEY=
OPENAI_API_KEY=

# --- Discovery ---
SERPER_API_KEY=

# --- Notifications ---
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_TOKEN=
WHATSAPP_RECIPIENT=

# --- Database ---
DATABASE_PATH=data/job_bot.db
VECTOR_STORE_PATH=data/vectors
```

- [ ] **Step 3: Create `job_bot/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Create `job_bot/__main__.py`**

```python
from job_bot.cli.commands import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Install dependencies and verify**

Run: `pip install -e ".[dev]"` or `pip install -r <(grep -A100 'dependencies = ' pyproject.toml | sed -n 's/^    "\(.*\)",*/\1/p')`

Run: `python -c "import job_bot; print(job_bot.__version__)"`
Expected: `0.1.0`

---

### Task 2: Configuration System

**Files:**
- Create: `job_bot/config.py`
- Create: `job_bot/config_default.yaml`

- [ ] **Step 1: Create default config YAML**

```yaml
# job_bot/config_default.yaml
profile:
  name: ""
  email: ""
  phone: ""
  cv_path: ""
  skills: []

llm:
  provider: ollama
  model: llama3.1:8b
  embedding_model: nomic-embed-text
  temperature: 0.3

discovery:
  interval_hours: 24
  sources:
    google_search: true
    linkedin: true
    indeed: false
    ycombinator: true
    grants: true
    companies: []
  serper_api_key: ""
  grants_keywords: []

application:
  human_approval: true
  max_applications_per_run: 5
  save_drafts: true
  headless: true

notifications:
  whatsapp:
    enabled: false
    phone_number_id: ""
    token: ""
    recipient: ""

database:
  path: "data/job_bot.db"
  vector_path: "data/vectors"
```

- [ ] **Step 2: Write `job_bot/config.py`**

```python
import os
from pathlib import Path
from typing import Any, Dict, Optional

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
    sources: Dict[str, bool] = Field(default_factory=lambda: {
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


def load_config(config_path: Optional[str] = None) -> Config:
    load_dotenv()
    path = Path(config_path) if config_path else (Path.cwd() / "config.yaml")
    if not path.exists():
        default = Path(__file__).parent / "config_default.yaml"
        with open(default) as f:
            data = yaml.safe_load(f)
    else:
        with open(path) as f:
            data = yaml.safe_load(f)
    data = _inject_env_vars(data)
    return Config(**data)


def _inject_env_vars(data: Dict[str, Any]) -> Dict[str, Any]:
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
```

- [ ] **Step 3: Test config loading**

Run: `python -c "from job_bot.config import load_config; c = load_config(); print(c.llm.model)"`
Expected: `llama3.1:8b`

---

### Task 3: Database Models and Repository

**Files:**
- Create: `job_bot/database/__init__.py`
- Create: `job_bot/database/models.py`
- Create: `job_bot/database/repository.py`

- [ ] **Step 1: Create `job_bot/database/models.py`**

```python
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, JSON, Enum, create_engine
)
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


class Opportunity(Base):
    __tablename__ = "opportunities"
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    company = Column(String(300), nullable=False)
    description = Column(Text)
    url = Column(String(2000))
    source = Column(String(100))
    deadline = Column(DateTime, nullable=True)
    salary_range = Column(String(200))
    location = Column(String(300))
    remote = Column(String(50))
    status = Column(String(50), default="new")
    score = Column(Float, nullable=True)
    matched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True)
    opportunity_id = Column(Integer, nullable=False)
    cover_letter = Column(Text)
    answers = Column(JSON)
    platform = Column(String(100))
    status = Column(String(50), default="draft")
    submitted_at = Column(DateTime, nullable=True)
    screenshot_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    action = Column(String(200), nullable=False)
    component = Column(String(100), nullable=False)
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Create `job_bot/database/repository.py`**

```python
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from job_bot.database.models import Base, Opportunity, Application, AuditLog


def init_db(db_path: str) -> str:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return f"sqlite:///{db_path}"


class Repository:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)

    def add_opportunity(self, opp: dict) -> int:
        with Session(self.engine) as session:
            existing = session.query(Opportunity).filter_by(url=opp.get("url")).first()
            if existing:
                return existing.id
            record = Opportunity(**opp)
            session.add(record)
            session.commit()
            return record.id

    def get_pending_opportunities(self, min_score: float = 0.0):
        with Session(self.engine) as session:
            return session.query(Opportunity).filter(
                Opportunity.status == "new",
                Opportunity.score >= min_score,
            ).all()

    def update_opportunity_status(self, opp_id: int, status: str):
        with Session(self.engine) as session:
            record = session.query(Opportunity).filter_by(id=opp_id).first()
            if record:
                record.status = status
                session.commit()

    def add_application(self, app_data: dict) -> int:
        with Session(self.engine) as session:
            record = Application(**app_data)
            session.add(record)
            session.commit()
            return record.id

    def log_audit(self, action: str, component: str, details: Optional[dict] = None):
        with Session(self.engine) as session:
            record = AuditLog(action=action, component=component, details=details or {})
            session.add(record)
            session.commit()

    def get_stats(self) -> dict:
        with Session(self.engine) as session:
            return {
                "total": session.query(Opportunity).count(),
                "new": session.query(Opportunity).filter_by(status="new").count(),
                "applied": session.query(Opportunity).filter_by(status="applied").count(),
            }
```

- [ ] **Step 3: Test database initialization**

Run: `python -c "from job_bot.database.repository import init_db, Repository; db_url = init_db('test.db'); repo = Repository(db_url); oid = repo.add_opportunity({'title': 'Test Job', 'company': 'TestCorp', 'url': 'http://example.com/job'}); print(f'Created opp {oid}'); print(repo.get_stats())"`
Expected: Opp created, stats printed

Run: `Remove-Item -LiteralPath 'test.db' -Force`

---

### Task 4: Utility Modules

**Files:**
- Create: `job_bot/utils/__init__.py`
- Create: `job_bot/utils/logging.py`
- Create: `job_bot/utils/retry.py`
- Create: `job_bot/utils/encryption.py`

- [ ] **Step 1: Create `job_bot/utils/logging.py`**

```python
import structlog


def setup_logging(level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "job_bot"):
    return structlog.get_logger(name)
```

- [ ] **Step 2: Create `job_bot/utils/retry.py`**

```python
import asyncio
import logging
from functools import wraps
from typing import Callable, Type

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 4.0,
    exceptions: tuple = (Exception,),
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_attempts:
                        logger.warning(
                            "retry_attempt",
                            func=func.__name__,
                            attempt=attempt,
                            delay=current_delay,
                            error=str(e),
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            raise last_error
        return wrapper
    return decorator
```

- [ ] **Step 3: Create `job_bot/utils/encryption.py`**

```python
from cryptography.fernet import Fernet
import os


def get_cipher() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key()
        os.environ["ENCRYPTION_KEY"] = key.decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return get_cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return get_cipher().decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 4: Verify imports work**

Run: `python -c "from job_bot.utils.logging import setup_logging, get_logger; from job_bot.utils.retry import retry; from job_bot.utils.encryption import encrypt, decrypt; print('Utils OK')"`
Expected: `Utils OK`

---

### Task 5: CLI Skeleton

**Files:**
- Create: `job_bot/cli/__init__.py`
- Create: `job_bot/cli/commands.py`

- [ ] **Step 1: Create `job_bot/cli/commands.py`**

```python
import typer
from pathlib import Path

from job_bot.config import load_config, Config
from job_bot.database.repository import init_db, Repository
from job_bot.utils.logging import setup_logging, get_logger

app = typer.Typer(name="job-bot", help="Automated job application bot")
logger = get_logger()


def _init() -> tuple[Config, Repository]:
    cfg = load_config()
    setup_logging()
    db_url = init_db(cfg.database.path)
    repo = Repository(db_url)
    return cfg, repo


@app.command()
def discover():
    """Run opportunity discovery now."""
    cfg, repo = _init()
    logger.info("discovery_started", sources=list(cfg.discovery.sources.keys()))
    typer.echo("Discovery run initiated. Check back for results.")


@app.command()
def review():
    """Review pending matches."""
    cfg, repo = _init()
    stats = repo.get_stats()
    typer.echo(f"Opportunities: {stats['total']} total, {stats['new']} new, {stats['applied']} applied")


@app.command()
def apply(opportunity_id: int = typer.Argument(..., help="Opportunity ID to apply to")):
    """Prepare and send an application."""
    cfg, repo = _init()
    typer.echo(f"Preparing application for opportunity #{opportunity_id}")


@app.command()
def status():
    """Show application tracking dashboard."""
    cfg, repo = _init()
    typer.echo(repo.get_stats())


@app.command()
def config():
    """Show current configuration."""
    cfg = load_config()
    typer.echo(cfg.model_dump_json(indent=2))


@app.command()
def profile():
    """Show configured profile."""
    cfg, repo = _init()
    typer.echo(f"Name: {cfg.profile.name}")
    typer.echo(f"Email: {cfg.profile.email}")
    typer.echo(f"Skills: {', '.join(cfg.profile.skills)}")
```

- [ ] **Step 2: Verify CLI works**

Run: `python -m job_bot --help`
Expected: Shows command list (discover, review, apply, status, config, profile)

Run: `python -m job_bot status`
Expected: Shows stats

- [ ] **Step 3: Create `config.yaml` in project root for local dev**

```yaml
profile:
  name: ""
  email: ""
  phone: ""
  cv_path: ""
  skills:
    - Python
    - React
    - AI/ML
    - Product Design

llm:
  provider: ollama
  model: llama3.1:8b
  embedding_model: nomic-embed-text
  temperature: 0.3

discovery:
  interval_hours: 24
  sources:
    google_search: true
    linkedin: true
    indeed: false
    ycombinator: true
    grants: true
    companies: []
  serper_api_key: "${SERPER_API_KEY}"
  grants_keywords:
    - AI research
    - tech fellowship
    - startup grant

application:
  human_approval: true
  max_applications_per_run: 5
  save_drafts: true
  headless: true

notifications:
  whatsapp:
    enabled: false
    phone_number_id: ""
    token: ""
    recipient: ""

database:
  path: "data/job_bot.db"
  vector_path: "data/vectors"
```

---

### Task 6: Tests Foundation

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Create `tests/test_config.py`**

```python
import pytest
from job_bot.config import Config, LLMConfig, load_config


class TestConfig:
    def test_default_config(self):
        cfg = load_config()
        assert isinstance(cfg, Config)
        assert cfg.llm.provider == "ollama"
        assert cfg.database.path == "data/job_bot.db"

    def test_llm_config_defaults(self):
        llm = LLMConfig()
        assert llm.model == "llama3.1:8b"
        assert llm.temperature == 0.3
```

- [ ] **Step 2: Create `tests/test_database.py`**

```python
import pytest
from pathlib import Path
from job_bot.database.repository import init_db, Repository


class TestDatabase:
    @pytest.fixture
    def repo(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db_url = init_db(db_path)
        return Repository(db_url)

    def test_add_and_get_opportunity(self, repo):
        oid = repo.add_opportunity({
            "title": "AI Engineer",
            "company": "OpenAI",
            "url": "https://openai.com/careers/123",
            "source": "company_pages",
            "remote": "Remote",
        })
        assert oid > 0

    def test_no_duplicates(self, repo):
        oid1 = repo.add_opportunity({
            "title": "Duplicate",
            "company": "X",
            "url": "https://x.com/job/1",
        })
        oid2 = repo.add_opportunity({
            "title": "Duplicate",
            "company": "X",
            "url": "https://x.com/job/1",
        })
        assert oid1 == oid2

    def test_stats(self, repo):
        repo.add_opportunity({"title": "Job 1", "company": "A", "url": "https://a.com/1"})
        repo.add_opportunity({"title": "Job 2", "company": "B", "url": "https://b.com/1"})
        stats = repo.get_stats()
        assert stats["total"] == 2
        assert stats["new"] == 2
```

- [ ] **Step 3: Run tests**

Run: `pip install pytest; python -m pytest tests/ -v`
Expected: All tests pass

---

### Task 7: Git Init + Commit

- [ ] **Step 1: Initialize git repository**

Run: `git init`

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# Environment
.env
*.key

# Data
data/
*.db

# Playwright browsers
node_modules/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Commit foundation**

```bash
git add .
git commit -m "feat: project foundation - config, database, CLI, utils"
```
