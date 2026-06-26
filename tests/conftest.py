import pytest
from job_bot.database.repository import init_db, Repository
from job_bot.database.models import Base, Opportunity


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    db_url = init_db(db_path)
    return Repository(db_url)


@pytest.fixture
def sample_opportunity():
    return {
        "title": "Software Engineer",
        "company": "Test Corp",
        "url": "https://example.com/job/123",
        "description": "A test job posting",
        "source": "test",
        "category": "job",
    }
