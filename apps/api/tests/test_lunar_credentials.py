from __future__ import annotations

import os

import pytest

from app.core.config import get_settings
from app.services.lunar_credentials import (
    LunarCredentialsError,
    assert_safe_log_message,
    credential_debug_safe_repr,
    get_credential_status,
    require_lunar_credentials,
)


def test_missing_credentials_fail_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUNAR_USERNAME", raising=False)
    monkeypatch.delenv("LUNAR_PASSWORD", raising=False)
    status = get_credential_status()
    assert status.credential_available is False
    with pytest.raises(LunarCredentialsError):
        require_lunar_credentials()


def test_present_credentials_available(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    status = get_credential_status()
    assert status.credential_available is True
    assert status.username_masked == "s********r"
    assert "secret-value" not in credential_debug_safe_repr()
    assert_safe_log_message("Lunar login succeeded for store-user")


def test_credentials_from_settings_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock, patch

    monkeypatch.delenv("LUNAR_USERNAME", raising=False)
    monkeypatch.delenv("LUNAR_PASSWORD", raising=False)
    get_settings.cache_clear()
    settings = Mock(lunar_username_raw="store-user", lunar_password_raw="secret-value")
    with patch("app.services.lunar_credentials.get_settings", return_value=settings):
        status = get_credential_status()
    assert status.credential_available is True
    assert "secret-value" not in credential_debug_safe_repr()
