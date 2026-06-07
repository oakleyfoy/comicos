"""Best-effort P90 reads — missing tables or empty data must not break collector surfaces."""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import DBAPIError, ProgrammingError, SQLAlchemyError
from sqlmodel import Session

logger = logging.getLogger(__name__)

T = TypeVar("T")


def p90_rollback_session(session: Session) -> None:
    try:
        session.rollback()
    except Exception:  # noqa: BLE001
        pass


def is_missing_relation_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg or "undefinedtable" in msg or "42p01" in msg


def p90_safe_call(session: Session, fn: Callable[[], T], *, default: T, label: str = "p90") -> T:
    try:
        return fn()
    except (ProgrammingError, DBAPIError, SQLAlchemyError) as exc:
        if is_missing_relation_error(exc) or "aborted" in str(exc).lower():
            logger.warning("%s read skipped (db): %s", label, exc)
        else:
            logger.warning("%s read failed: %s", label, exc)
        p90_rollback_session(session)
        return default
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s read failed: %s", label, exc)
        p90_rollback_session(session)
        return default
