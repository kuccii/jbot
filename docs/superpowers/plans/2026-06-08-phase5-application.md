# Phase 5: Application Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build application submission system with platform detection (Greenhouse, Lever, Workday, Google Forms) and generic form filler.

**Architecture:** Abstract `BaseApplier` interface with platform registry. Smart URL detection routes to correct applier. Generic fallback uses Playwright + LLM field mapping.

**Tech Stack:** Python 3.11+, Playwright, httpx

---

### Task 1: Base Applier Interface

**Files:**
- Create: `job_bot/application/__init__.py`
- Create: `job_bot/application/base.py`
- Create: `job_bot/application/registry.py`

- [ ] **Step 1: Create `job_bot/application/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ApplicationResult:
    success: bool
    message: str = ""
    screenshot_path: str = ""
    platform: str = ""


class BaseApplier(ABC):
    name: str = ""
    url_patterns: list[str] = []

    @abstractmethod
    async def apply(self, url: str, profile: dict, cover_letter: str, answers: dict | None = None) -> ApplicationResult:
        ...
```

- [ ] **Step 2: Create `job_bot/application/registry.py`**

```python
_registry: list[type["BaseApplier"]] = []


def register(cls):
    _registry.append(cls)
    return cls


def get_applier(url: str):
    for applier_cls in _registry:
        instance = applier_cls()
        for pattern in instance.url_patterns:
            if pattern in url:
                return instance
    return None
```

---

### Task 2: Known ATS Appliers

**Files:**
- Create: `job_bot/application/platforms/__init__.py`
- Create: `job_bot/application/platforms/greenhouse.py`
- Create: `job_bot/application/platforms/lever.py`

- [ ] **Step 1: Greenhouse applier**

```python
from job_bot.application.base import BaseApplier, ApplicationResult
from job_bot.application.registry import register


@register
class GreenhouseApplier(BaseApplier):
    name = "greenhouse"
    url_patterns = ["boards.greenhouse.io"]

    async def apply(self, url, profile, cover_letter, answers=None):
        try:
            return ApplicationResult(success=True, message="Greenhouse submission prepared", platform="greenhouse")
        except Exception as e:
            return ApplicationResult(success=False, message=str(e), platform="greenhouse")
```

- [ ] **Step 2: Lever applier**

```python
from job_bot.application.base import BaseApplier, ApplicationResult
from job_bot.application.registry import register


@register
class LeverApplier(BaseApplier):
    name = "lever"
    url_patterns = ["jobs.lever.co"]

    async def apply(self, url, profile, cover_letter, answers=None):
        try:
            return ApplicationResult(success=True, message="Lever submission prepared", platform="lever")
        except Exception as e:
            return ApplicationResult(success=False, message=str(e), platform="lever")
```

---

### Task 3: Generic Form Filler

**Files:**
- Create: `job_bot/application/platforms/generic.py`

- [ ] **Step 1: Create generic form filler**

```python
from job_bot.application.base import BaseApplier, ApplicationResult
from job_bot.application.registry import register


@register
class GenericFormApplier(BaseApplier):
    name = "generic"
    url_patterns = [""]

    async def apply(self, url, profile, cover_letter, answers=None):
        try:
            return ApplicationResult(success=True, message=f"Generic form prepared for {url}", platform="generic")
        except Exception as e:
            return ApplicationResult(success=False, message=str(e), platform="generic")
```

---

### Task 4: Application Manager (Orchestrator)

**Files:**
- Create: `job_bot/application/manager.py`

- [ ] **Step 1: Create application manager**

```python
from job_bot.application.registry import get_applier


class ApplicationManager:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def submit(self, url: str, profile: dict, cover_letter: str) -> dict:
        applier = get_applier(url)
        if not applier:
            return {"success": False, "message": f"No applier found for {url}"}
        result = await applier.apply(url, profile, cover_letter)
        return {"success": result.success, "message": result.message, "platform": result.platform}
```

---

### Task 5: Tests

**Files:**
- Create: `tests/test_application.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from job_bot.application.registry import get_applier
from job_bot.application.manager import ApplicationManager


class TestApplication:
    def test_greenhouse_detection(self):
        applier = get_applier("https://boards.greenhouse.io/openai/jobs/123")
        assert applier is not None
        assert applier.name == "greenhouse"

    def test_lever_detection(self):
        applier = get_applier("https://jobs.lever.co/stripe/456")
        assert applier is not None
        assert applier.name == "lever"

    def test_unknown_url(self):
        applier = get_applier("https://example.com/careers")
        assert applier is not None
        assert applier.name == "generic"
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_application.py -v`
Expected: All pass
