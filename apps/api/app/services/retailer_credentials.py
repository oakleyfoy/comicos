from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_MISSING_KEY_MESSAGE = (
    "RETAILER_CREDENTIAL_ENCRYPTION_KEY is required for retailer account save, "
    "test, and sync operations."
)


class RetailerCredentialError(RuntimeError):
    """Raised when retailer credentials cannot be encrypted or decrypted safely."""


class RetailerCredentialKeyMissingError(RetailerCredentialError):
    """Raised when the dedicated retailer credential key is not configured."""


def _require_key() -> str:
    settings = get_settings()
    key = settings.retailer_credential_encryption_key.strip()
    if key:
        return key
    if settings.app_env.lower() == "test":
        return ""
    raise RetailerCredentialKeyMissingError(_MISSING_KEY_MESSAGE)


def retailer_credential_key_configured() -> bool:
    return bool(get_settings().retailer_credential_encryption_key.strip())


def validate_retailer_credential_key() -> bool:
    key = _require_key()
    if not key:
        return False
    try:
        Fernet(key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise RetailerCredentialError(
            "RETAILER_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc
    return True


def _get_cipher() -> Fernet:
    key = _require_key()
    if not key:
        raise RetailerCredentialKeyMissingError(_MISSING_KEY_MESSAGE)
    try:
        return Fernet(key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise RetailerCredentialError(
            "RETAILER_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc


@dataclass(slots=True)
class DecryptedRetailerCredentials:
    username: str
    password: str
    credential_version: int


def encrypt_retailer_password(password: str) -> str:
    value = password.strip()
    if not value:
        raise RetailerCredentialError("Retailer password is required.")
    return _get_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_retailer_password(encrypted_password: str) -> str:
    try:
        return _get_cipher().decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RetailerCredentialError("Stored retailer password could not be decrypted.") from exc


def mask_retailer_username(username: str) -> str:
    value = username.strip()
    if not value:
        return ""
    if "@" in value:
        local, _, domain = value.partition("@")
        if len(local) <= 2:
            masked_local = local[:1] + "*" * max(len(local) - 1, 1)
        else:
            masked_local = local[:2] + "*" * max(len(local) - 2, 2)
        return f"{masked_local}@{domain}"
    if len(value) <= 4:
        return value[:1] + "*" * max(len(value) - 1, 1)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
