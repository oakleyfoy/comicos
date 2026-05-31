from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.core.config import get_settings


class LunarCredentialsError(Exception):
    """Raised when Lunar credentials are missing or invalid."""


def _mask_username(username: str) -> str:
    cleaned = username.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 2:
        return "*" * len(cleaned)
    return f"{cleaned[0]}{'*' * (len(cleaned) - 2)}{cleaned[-1]}"


@dataclass(frozen=True)
class LunarCredentialStatus:
    credential_available: bool
    username_masked: str | None


def get_lunar_username() -> str | None:
    value = os.environ.get("LUNAR_USERNAME", "").strip()
    if not value:
        value = get_settings().lunar_username_raw.strip()
    return value or None


def get_lunar_password() -> str | None:
    value = os.environ.get("LUNAR_PASSWORD", "").strip()
    if not value:
        value = get_settings().lunar_password_raw.strip()
    return value or None


def require_lunar_credentials() -> tuple[str, str]:
    username = get_lunar_username()
    password = get_lunar_password()
    if not username or not password:
        raise LunarCredentialsError("LUNAR_USERNAME and LUNAR_PASSWORD must be set in the environment")
    return username, password


def get_credential_status() -> LunarCredentialStatus:
    username = get_lunar_username()
    password = get_lunar_password()
    available = bool(username and password)
    return LunarCredentialStatus(
        credential_available=available,
        username_masked=_mask_username(username) if username else None,
    )


def credential_debug_safe_repr() -> str:
    status = get_credential_status()
    return f"LunarCredentialStatus(available={status.credential_available}, username={status.username_masked!r})"


PASSWORD_PATTERN = re.compile(r"(password|passwd|secret)", re.IGNORECASE)


def assert_safe_log_message(message: str) -> None:
    if get_lunar_password() and get_lunar_password() in message:
        raise ValueError("Refusing to log raw Lunar password")
