from collections.abc import Generator
from functools import lru_cache

from sqlmodel import Session, create_engine

from app.core.config import get_settings


@lru_cache
def get_engine():
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )

    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
