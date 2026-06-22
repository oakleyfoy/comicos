"""Detect whether legacy customer-order spine tables still exist (post–Phase D teardown)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import inspect
from sqlmodel import Session


@lru_cache(maxsize=1)
def _legacy_spine_table_names() -> frozenset[str] | None:
    return None


def refresh_legacy_spine_cache() -> None:
    _legacy_spine_table_names.cache_clear()


def legacy_customer_order_table_exists(session: Session) -> bool:
    bind = session.get_bind()
    names = inspect(bind).get_table_names()
    return "customer_order" in names


def legacy_comic_issue_table_exists(session: Session) -> bool:
    bind = session.get_bind()
    return "comic_issue" in inspect(bind).get_table_names()


def legacy_variant_table_exists(session: Session) -> bool:
    bind = session.get_bind()
    return "variant" in inspect(bind).get_table_names()
