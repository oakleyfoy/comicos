"""Resolve owner user id by email (same patterns as verify_cross_system_owner.py)."""

from __future__ import annotations

from sqlalchemy import select
from sqlmodel import Session

from app.models import User


def scalar_value(value: object | None) -> object | None:
    if value is None:
        return None
    if hasattr(value, "_mapping"):
        return value[0]
    if isinstance(value, tuple):
        return value[0]
    return value


def unwrap_user_row(row: object | None) -> object | None:
    if row is None:
        return None
    unwrapped = scalar_value(row)
    if unwrapped is None:
        return None
    if hasattr(unwrapped, "_mapping"):
        return unwrapped[0]
    return unwrapped


def user_id_from_object(user: object) -> int | None:
    if user is None:
        return None
    if hasattr(user, "id"):
        raw = getattr(user, "id", None)
        if raw is not None:
            return int(raw)
    mapping = getattr(user, "_mapping", None)
    if mapping is not None:
        for key in ("id", "user_id"):
            if key in mapping and mapping[key] is not None:
                return int(mapping[key])
    getter = getattr(user, "__getitem__", None)
    if getter is not None:
        try:
            return int(getter("id"))
        except (KeyError, TypeError, ValueError):
            pass
    return None


def resolve_owner_user_id(session: Session, email: str) -> int:
    """Resolve owner_user_id from email using the app's User model."""
    normalized = email.strip()
    if not normalized:
        raise ValueError("email is required")

    user_row = session.exec(select(User).where(User.email == normalized)).one_or_none()
    user = unwrap_user_row(user_row)
    if user is not None:
        uid = user_id_from_object(user)
        if uid is not None and uid > 0:
            return uid

    scalar_row = session.exec(select(User.id).where(User.email == normalized)).one_or_none()
    scalar = scalar_value(scalar_row)
    if scalar is not None:
        uid = int(scalar)
        if uid > 0:
            return uid

    raise LookupError(f"no user found for email={normalized!r}")
