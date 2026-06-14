"""Database URL resolution for P97 CLI scripts (aligned with progress_watch)."""
from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from p97_bootstrap import API_ROOT

# Same default as scripts/p97_progress_watch.py
DEFAULT_P97_DATABASE_URL = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"


def ensure_p97_env_loaded() -> None:
    """Load apps/api/.env only — avoid alternate companion installs overriding catalog DB."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    api_env = API_ROOT / ".env"
    if api_env.is_file():
        load_dotenv(api_env, override=False)


def resolve_p97_database_url(cli_database_url: str | None = None) -> str:
    if cli_database_url and cli_database_url.strip():
        return cli_database_url.strip()
    ensure_p97_env_loaded()
    env_url = (os.environ.get("DATABASE_URL") or "").strip()
    if env_url:
        return env_url
    return DEFAULT_P97_DATABASE_URL


def describe_database_url(url: str) -> str:
    if "@" in url:
        return url.split("@", 1)[1]
    return url


@lru_cache
def get_p97_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)
