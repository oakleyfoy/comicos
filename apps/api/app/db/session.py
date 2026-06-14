from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.config import get_settings


@event.listens_for(Engine, "connect")
def _sqlite_enable_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
    dialect = getattr(connection_record, "dialect", None)
    if getattr(dialect, "name", None) == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=120000")
        cursor.close()


@lru_cache
def get_engine():
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False, "timeout": 120}
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
