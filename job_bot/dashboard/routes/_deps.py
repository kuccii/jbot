"""Shared dependencies for dashboard routes."""

from job_bot.config import load_config
from job_bot.database.repository import init_db, Repository

_last_run = {"discovery": None, "review": None, "status": "idle"}


def get_repo() -> Repository:
    cfg = load_config()
    db_url = init_db(cfg.database.path)
    return Repository(db_url)
