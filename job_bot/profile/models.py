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
