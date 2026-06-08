# Phase 6: Notifications & Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build WhatsApp notifications via Meta Cloud API, interactive review workflow, and end-to-end integration.

**Architecture:** Abstract `BaseNotifier` interface. WhatsApp notifier sends templates for new matches, draft ready, submission results. CLI review commands for human-in-the-loop approval.

**Tech Stack:** Python 3.11+, httpx, Typer

---

### Task 1: Notifier Interface

**Files:**
- Create: `job_bot/notifications/__init__.py`
- Create: `job_bot/notifications/base.py`

- [ ] **Step 1: Create base notifier**

```python
from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    @abstractmethod
    async def send_message(self, to: str, text: str) -> bool:
        ...

    @abstractmethod
    async def send_template(self, to: str, template_name: str, params: dict) -> bool:
        ...
```

---

### Task 2: WhatsApp Notifier

**Files:**
- Create: `job_bot/notifications/whatsapp.py`

- [ ] **Step 1: Create WhatsApp notifier**

```python
import httpx
from job_bot.notifications.base import BaseNotifier


class WhatsAppNotifier(BaseNotifier):
    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, phone_number_id: str, token: str):
        self.phone_number_id = phone_number_id
        self.token = token

    async def send_message(self, to: str, text: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/{self.phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text},
                },
            )
            return resp.status_code == 200

    async def send_template(self, to: str, template_name: str, params: dict) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/{self.phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": "en"},
                        "components": [{
                            "type": "body",
                            "parameters": [{"type": "text", "text": v} for v in params.values()],
                        }],
                    },
                },
            )
            return resp.status_code == 200
```

---

### Task 3: Interactive Review Workflow

**Files:**
- Create: `job_bot/review/__init__.py`
- Create: `job_bot/review/manager.py`

- [ ] **Step 1: Create review manager**

```python
from job_bot.database.repository import Repository
from job_bot.intelligence.drafter import Drafter
from job_bot.intelligence.matcher import Matcher


class ReviewManager:
    def __init__(self, repo: Repository, matcher: Matcher, drafter: Drafter):
        self.repo = repo
        self.matcher = matcher
        self.drafter = drafter

    async def review_pending(self, profile: dict):
        pending = self.repo.get_pending_opportunities(min_score=0.3)
        reviews = []
        for opp in pending:
            score = await self.matcher.score(
                profile.get("cv_text", ""),
                f"{opp.title} {opp.description}",
            )
            cover = await self.drafter.generate_cover_letter(
                profile.get("cv_text", ""),
                opp.title,
                opp.company,
                profile.get("skills", []),
            )
            reviews.append({"opportunity": opp, "score": score, "cover_letter": cover})
        return reviews
```

---

### Task 4: E2E Pipeline

**Files:**
- Create: `job_bot/pipeline.py`

- [ ] **Step 1: Create end-to-end pipeline**

```python
from job_bot.config import Config
from job_bot.database.repository import Repository
from job_bot.discovery.orchestrator import DiscoveryOrchestrator
from job_bot.intelligence.providers.factory import create_provider
from job_bot.intelligence.matcher import Matcher
from job_bot.intelligence.drafter import Drafter
from job_bot.review.manager import ReviewManager
from job_bot.application.manager import ApplicationManager


class Pipeline:
    def __init__(self, config: Config, repo: Repository):
        self.config = config
        self.repo = repo
        provider = create_provider(config.llm.provider, model=config.llm.model)
        self.matcher = Matcher(provider)
        self.drafter = Drafter(provider)
        self.review_manager = ReviewManager(repo, self.matcher, self.drafter)
        self.application_manager = ApplicationManager(headless=config.application.headless)

    async def run_full_cycle(self):
        # 1. Discover
        orch = DiscoveryOrchestrator(self.repo, self.config.discovery.model_dump())
        opportunities = await orch.run_all()

        # 2. Match & draft (for human review)
        profile = {"cv_text": "", "skills": self.config.profile.skills}
        reviews = await self.review_manager.review_pending(profile)

        return {"discovered": len(opportunities), "reviews": len(reviews)}
```

---

### Task 5: Update CLI with Full Commands

**Files:**
- Modify: `job_bot/cli/commands.py`

- [ ] **Step 1: Update review and apply commands**

```python
@app.command()
def review():
    """Review pending matches with AI scores and drafts."""
    cfg, repo = _init()
    from job_bot.pipeline import Pipeline
    import asyncio
    pipeline = Pipeline(cfg, repo)
    results = asyncio.run(pipeline.run_full_cycle())
    typer.echo(f"Review ready: {results}")

@app.command()
def apply(opportunity_id: int = typer.Argument(...)):
    """Prepare and submit application for an opportunity."""
    cfg, repo = _init()
    from job_bot.pipeline import Pipeline
    import asyncio
    pipeline = Pipeline(cfg, repo)
    result = asyncio.run(pipeline.application_manager.submit(
        "url", {"name": cfg.profile.name, "email": cfg.profile.email}, "cover letter"
    ))
    typer.echo(f"Application result: {result}")
```

---

### Task 6: Tests

**Files:**
- Create: `tests/test_notifications.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from job_bot.notifications.base import BaseNotifier


class FakeNotifier(BaseNotifier):
    async def send_message(self, to, text):
        return True
    async def send_template(self, to, name, params):
        return True


class TestNotifications:
    def test_fake_notifier(self):
        n = FakeNotifier()
        import asyncio
        assert asyncio.run(n.send_message("+123", "Hello"))
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All pass
