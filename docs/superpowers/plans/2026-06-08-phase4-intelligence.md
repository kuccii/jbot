# Phase 4: Intelligence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build LLM provider abstraction (Ollama + Gemini), opportunity matching, and cover letter drafting.

**Architecture:** Abstract `LLMProvider` interface with runtime-selectable providers. Matcher scores opportunities against profile. Drafter generates tailored cover letters.

**Tech Stack:** Python 3.11+, httpx, pydantic

---

### Task 1: LLM Provider Interface

**Files:**
- Create: `job_bot/intelligence/__init__.py`
- Create: `job_bot/intelligence/providers/__init__.py`

- [ ] **Step 1: Create provider base**

```python
# job_bot/intelligence/providers/base.py
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = ""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...
```

---

### Task 2: Ollama Provider

**Files:**
- Create: `job_bot/intelligence/providers/ollama.py`

- [ ] **Step 1: Implement Ollama provider**

```python
from job_bot.intelligence.providers.base import LLMProvider
import httpx


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def generate(self, prompt: str, system: str | None = None) -> str:
        async with httpx.AsyncClient() as client:
            payload = {"model": self.model, "prompt": prompt, "stream": False}
            if system:
                payload["system"] = system
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            return resp.json().get("response", "")

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            return resp.json().get("embedding", [])

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/api/tags", timeout=2)
                return resp.status_code == 200
        except Exception:
            return False
```

---

### Task 3: Gemini Provider

**Files:**
- Create: `job_bot/intelligence/providers/gemini.py`

- [ ] **Step 1: Implement Gemini provider**

```python
from job_bot.intelligence.providers.base import LLMProvider
import httpx


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-1.5-flash", api_key: str = ""):
        self.model = model
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def generate(self, prompt: str, system: str | None = None) -> str:
        async with httpx.AsyncClient() as client:
            contents = []
            if system:
                contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            resp = await client.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json={"contents": contents},
            )
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return ""

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/models/text-embedding-004:embedContent",
                params={"key": self.api_key},
                json={"content": {"parts": [{"text": text}]}},
            )
            return resp.json().get("embedding", {}).get("values", [])

    async def is_available(self) -> bool:
        return bool(self.api_key)
```

---

### Task 4: Provider Factory

**Files:**
- Create: `job_bot/intelligence/providers/factory.py`

- [ ] **Step 1: Create factory**

```python
from job_bot.intelligence.providers.base import LLMProvider
from job_bot.intelligence.providers.ollama import OllamaProvider
from job_bot.intelligence.providers.gemini import GeminiProvider


_PROVIDERS = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
}


def create_provider(name: str, **kwargs) -> LLMProvider:
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Options: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[name](**kwargs)
```

---

### Task 5: Matcher

**Files:**
- Create: `job_bot/intelligence/matcher.py`

- [ ] **Step 1: Implement matcher**

```python
from job_bot.intelligence.providers.base import LLMProvider


class Matcher:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def score(self, profile_text: str, opportunity_text: str) -> float:
        prompt = f"""Rate fit (0-100) between this profile and opportunity.

Profile: {profile_text[:1000]}

Opportunity: {opportunity_text[:1000]}

Return only a number 0-100."""
        result = await self.provider.generate(prompt)
        try:
            return min(100, max(0, float(result.strip()))) / 100
        except ValueError:
            return 0.0
```

---

### Task 6: Cover Letter Drafter

**Files:**
- Create: `job_bot/intelligence/drafter.py`

- [ ] **Step 1: Implement drafter**

```python
from job_bot.intelligence.providers.base import LLMProvider


class Drafter:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_cover_letter(
        self, profile: str, opportunity_title: str, company: str, skills: list[str]
    ) -> str:
        prompt = f"""Write a short cover letter for:
Position: {opportunity_title} at {company}
Skills: {', '.join(skills)}
Profile: {profile[:500]}

Keep it professional, 3-4 paragraphs. Highlight relevant experience."""
        return await self.provider.generate(prompt)
```

---

### Task 7: Tests

**Files:**
- Create: `tests/test_intelligence.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from job_bot.intelligence.providers.factory import create_provider
from job_bot.intelligence.matcher import Matcher
from job_bot.intelligence.drafter import Drafter


class TestProviders:
    def test_factory_ollama(self):
        provider = create_provider("ollama", model="llama3.1:8b")
        assert provider.name == "ollama"

    def test_factory_gemini(self):
        provider = create_provider("gemini", api_key="test")
        assert provider.name == "gemini"

    def test_factory_invalid(self):
        with pytest.raises(ValueError):
            create_provider("invalid")


class TestMatcher:
    def test_matcher_creation(self):
        provider = create_provider("ollama")
        matcher = Matcher(provider)
        assert matcher is not None


class TestDrafter:
    def test_drafter_creation(self):
        provider = create_provider("ollama")
        drafter = Drafter(provider)
        assert drafter is not None
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_intelligence.py -v`
Expected: All pass
