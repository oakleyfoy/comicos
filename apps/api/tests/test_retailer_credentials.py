from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.retailer_credentials import (
    RetailerCredentialError,
    RetailerCredentialKeyMissingError,
    decrypt_retailer_password,
    encrypt_retailer_password,
    mask_retailer_username,
    validate_retailer_credential_key,
)


def test_encrypt_and_decrypt_retailer_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv(
        "RETAILER_CREDENTIAL_ENCRYPTION_KEY", "V6cEMuP6xFZqlkGriZpFMUJsbgx5caX5-CQ1e5rjXQM="
    )
    get_settings.cache_clear()
    encrypted = encrypt_retailer_password("supersafe")
    assert encrypted != "supersafe"
    assert decrypt_retailer_password(encrypted) == "supersafe"


def test_missing_key_raises_outside_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("RETAILER_CREDENTIAL_ENCRYPTION_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RetailerCredentialKeyMissingError):
        validate_retailer_credential_key()


def test_invalid_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RETAILER_CREDENTIAL_ENCRYPTION_KEY", "not-a-key")
    get_settings.cache_clear()
    with pytest.raises(RetailerCredentialError):
        validate_retailer_credential_key()


def test_mask_retailer_username() -> None:
    assert mask_retailer_username("collector@example.com").startswith("co")
    assert "*" in mask_retailer_username("collector@example.com")
