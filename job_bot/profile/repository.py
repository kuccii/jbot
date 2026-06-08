import sqlite3
from datetime import datetime
from pathlib import Path

from job_bot.profile.models import UserProfile


class ProfileRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_table()

    def _init_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY,
                    name TEXT, email TEXT, phone TEXT,
                    bio TEXT, skills TEXT, cv_text TEXT,
                    preferences TEXT, updated_at TEXT
                )
            """)

    def save(self, profile: UserProfile) -> None:
        data = profile.model_dump()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_profile")
            conn.execute(
                "INSERT INTO user_profile (name, email, phone, bio, skills, cv_text, preferences, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (data["name"], data["email"], data["phone"], data["bio"],
                 ",".join(data["skills"]), data["cv_text"], str(data["preferences"]),
                 datetime.utcnow().isoformat()),
            )

    def load(self) -> UserProfile | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM user_profile LIMIT 1").fetchone()
        if not row:
            return None
        return UserProfile(
            name=row[1], email=row[2], phone=row[3], bio=row[4],
            skills=row[5].split(",") if row[5] else [],
            cv_text=row[6] or "",
        )
