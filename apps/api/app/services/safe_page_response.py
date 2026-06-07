"""Safe envelopes for visible nav GET APIs — never leak raw SQL to clients."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlmodel import Session

from app.schemas.scan_api_v1 import ScanApiV1Envelope, build_meta, wrap_object, wrap_standard_list

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

_LIST_PATH_MARKERS = (
    "/opportunities",
    "/sell-queue",
    "/listing-drafts",
    "/listings",
    "/queue",
    "/locations",
    "/future-pull-list",
    "/notifications",
    "/pull-lists",
    "/want-lists",
    "/daily-actions",
    "/mobile/scans",
    "/storage/audits",
    "/discovery/opportunities",
    "/discovery/watchlists",
    "/discovery/alerts",
)

_LEGACY_SAFE_GET_PREFIXES = (
    "/api/v1/",
    "/portfolio-strategy-dashboard",
    "/imports",
    "/gmail/",
)


def classify_page_error(exc: BaseException) -> tuple[str, str]:
    text = str(exc).lower()
    if "does not exist" in text and "relation" in text:
        return "ERROR", "Missing migration or snapshot table"
    if "undefinedtable" in text or "undefined table" in text:
        return "ERROR", "Missing migration or snapshot table"
    if "no such table" in text:
        return "ERROR", "Missing migration or snapshot table"
    if "pg8000" in text or "sqlalchemy" in exc.__class__.__module__.lower():
        return "ERROR", "Database temporarily unavailable"
    message = str(exc).strip()[:240] or exc.__class__.__name__
    return "ERROR", message


def is_safe_get_path(path: str) -> bool:
    if path in {"/health", "/health/db", "/health/auth-schema"}:
        return False
    return path.startswith(_LEGACY_SAFE_GET_PREFIXES) or any(
        path.startswith(p) for p in ("/api/v1/", "/portfolio-strategy-dashboard")
    )


def path_prefers_list_envelope(path: str) -> bool:
    return any(marker in path for marker in _LIST_PATH_MARKERS)


def build_safe_get_envelope(
    *,
    path: str,
    owner_user_id: int | str | None,
    exc: BaseException | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    status, default_msg = classify_page_error(exc) if exc else ("ERROR", message or "Unavailable")
    msg = message or default_msg
    if path_prefers_list_envelope(path):
        data: dict[str, Any] = {
            "items": [],
            "pagination": {
                "total_count": 0,
                "limit": 50,
                "offset": 0,
                "has_next": False,
                "next_cursor": None,
            },
            "status": status,
            "message": msg,
        }
    else:
        data = {"status": status, "message": msg}
    envelope = ScanApiV1Envelope(data=data, meta=build_meta(owner_user_id=owner_user_id))
    return envelope.model_dump(mode="json")


def run_safe_page_build(
    name: str,
    build: Callable[[], _T],
    *,
    fallback: Callable[[str, str], _T],
) -> _T:
    try:
        return build()
    except Exception as exc:  # noqa: BLE001
        status, msg = classify_page_error(exc)
        logger.exception("safe_page_build %s failed status=%s", name, status)
        return fallback(status, msg)


def safe_wrap_object_route(
    session: Session,
    *,
    owner_user_id: int,
    name: str,
    build: Callable[[], BaseModel],
    fallback: Callable[[str, str], BaseModel],
) -> ScanApiV1Envelope:
    body = run_safe_page_build(name, build, fallback=fallback)
    return wrap_object(body, owner_user_id=owner_user_id)


def safe_wrap_list_route(
    session: Session,
    *,
    owner_user_id: int,
    name: str,
    build: Callable[[], BaseModel],
    fallback: Callable[[str, str], BaseModel],
) -> ScanApiV1Envelope:
    body = run_safe_page_build(name, build, fallback=fallback)
    return wrap_standard_list(body, owner_user_id=owner_user_id)
