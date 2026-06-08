import pytest
from job_bot.profile.models import UserProfile
from job_bot.profile.cv_parser import extract_text
from pathlib import Path


class TestUserProfile:
    def test_defaults(self):
        p = UserProfile()
        assert p.name == ""
        assert p.skills == []

    def test_with_data(self):
        p = UserProfile(name="Alice", skills=["Python", "AI"])
        assert p.name == "Alice"
        assert len(p.skills) == 2


class TestCVParser:
    def test_txt_file(self, tmp_path):
        f = tmp_path / "cv.txt"
        f.write_text("My CV content", encoding="utf-8")
        text = extract_text(str(f))
        assert "My CV" in text

    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            extract_text("nonexistent.txt")

    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "cv.pdf"
        f.write_text("fake", encoding="utf-8")
        with pytest.raises(ValueError):
            extract_text(str(f))
