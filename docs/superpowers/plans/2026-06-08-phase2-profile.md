# Phase 2: Profile & Vector Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build user profile management (CV import, bio, skills) with ChromaDB vector store for semantic matching.

**Architecture:** Profile module stores user data in SQLite + ChromaDB. CV parsing extracts text from PDF/docx. Embeddings generated via sentence-transformers for similarity search against opportunities.

**Tech Stack:** Python 3.11+, ChromaDB, sentence-transformers, PyMuPDF (fitz), python-docx

---

### Task 1: Profile Models and Repository

**Files:**
- Create: `job_bot/profile/__init__.py`
- Create: `job_bot/profile/models.py`
- Create: `job_bot/profile/repository.py`

- [ ] **Step 1: Create `job_bot/profile/models.py`**

```python
from datetime import datetime
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    bio: str = ""
    skills: list[str] = Field(default_factory=list)
    cv_text: str = ""
    cv_path: str = ""
    preferences: dict = Field(default_factory=lambda: {
        "remote_only": True,
        "min_salary": 0,
        "locations": [],
        "job_types": ["contract", "freelance", "full-time"],
    })
    updated_at: str = ""


class ProfileRepository:
    def __init__(self, repo):
        self.repo = repo

    def save(self, profile: UserProfile) -> None:
        data = profile.model_dump()
        self.repo.db.execute("DELETE FROM user_profile")
        self.repo.db.execute(
            "INSERT INTO user_profile (name, email, phone, bio, skills, cv_text, preferences) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data["name"], data["email"], data["phone"], data["bio"],
             ",".join(data["skills"]), data["cv_text"], str(data["preferences"])),
        )

    def load(self) -> UserProfile | None:
        row = self.repo.db.execute("SELECT * FROM user_profile LIMIT 1").fetchone()
        if not row:
            return None
        return UserProfile(
            name=row[1], email=row[2], phone=row[3], bio=row[4],
            skills=row[5].split(",") if row[5] else [],
            cv_text=row[6] or "",
        )
```

- [ ] **Step 2: Create `job_bot/profile/__init__.py`** (empty)

---

### Task 2: CV Parser

**Files:**
- Create: `job_bot/profile/cv_parser.py`

- [ ] **Step 1: Create CV parser**

```python
from pathlib import Path


def extract_text(cv_path: str) -> str:
    path = Path(cv_path)
    if not path.exists():
        raise FileNotFoundError(f"CV not found: {cv_path}")
    if path.suffix == ".pdf":
        return _extract_pdf(path)
    elif path.suffix == ".docx":
        return _extract_docx(path)
    elif path.suffix == ".txt":
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported format: {path.suffix}")


def _extract_pdf(path: Path) -> str:
    import fitz
    text = []
    with fitz.open(path) as doc:
        for page in doc:
            text.append(page.get_text())
    return "\n".join(text)


def _extract_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)
```

---

### Task 3: Vector Store (ChromaDB)

**Files:**
- Create: `job_bot/profile/vector_store.py`

- [ ] **Step 1: Create vector store module**

```python
from pathlib import Path
import chromadb
from chromadb.config import Settings


class VectorStore:
    def __init__(self, persist_path: str):
        self.client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False),
        )

    def store_profile(self, profile_id: str, text: str, metadata: dict):
        col = self.client.get_or_create_collection("profiles")
        col.upsert(
            ids=[profile_id],
            documents=[text],
            metadatas=[metadata],
        )

    def search_similar(self, query: str, n_results: int = 5):
        col = self.client.get_or_create_collection("profiles")
        results = col.query(query_texts=[query], n_results=n_results)
        return results
```

---

### Task 4: Profile CLI Commands

**Files:**
- Modify: `job_bot/cli/commands.py`

- [ ] **Step 1: Add profile import command**

Add to `commands.py`:
```python
@app.command()
def import_cv(cv_path: str = typer.Argument(..., help="Path to CV file")):
    """Import CV and extract text."""
    from job_bot.profile.cv_parser import extract_text
    text = extract_text(cv_path)
    cfg, repo = _init()
    ProfileRepository(repo).save(UserProfile(cv_text=text, cv_path=cv_path))
    typer.echo(f"Imported CV ({len(text)} chars)")
```

---

### Task 5: Tests

**Files:**
- Create: `tests/test_profile.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from job_bot.profile.models import UserProfile


class TestUserProfile:
    def test_defaults(self):
        p = UserProfile()
        assert p.name == ""
        assert p.skills == []

    def test_with_data(self):
        p = UserProfile(name="Alice", skills=["Python", "AI"])
        assert p.name == "Alice"
        assert len(p.skills) == 2
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_profile.py -v`
Expected: All pass
