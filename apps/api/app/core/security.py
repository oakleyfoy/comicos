from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.core.config import get_settings

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = issued_at + expires_delta
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": issued_at,
        "jti": sha256(f"{subject}:{issued_at.isoformat()}".encode("utf-8")).hexdigest()[:24],
    }

    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def token_expiration_utc(token: str) -> datetime:
    payload = decode_access_token(token)
    exp = payload.get("exp")
    if isinstance(exp, datetime):
        return exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(exp, tz=timezone.utc)
    raise ValueError("Access token is missing a valid expiration claim")


def create_oauth_state_token(
    *,
    user_id: int,
    provider: str,
    redirect_origin: str | None = None,
    redirect_path: str | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "sub": str(user_id),
        "provider": provider,
        "purpose": "oauth_state",
        "exp": expire,
    }
    if redirect_origin:
        payload["redirect_origin"] = redirect_origin
    if redirect_path:
        payload["redirect_path"] = redirect_path
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_oauth_state_token(token: str) -> dict:
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("purpose") != "oauth_state":
        raise jwt.InvalidTokenError("Invalid OAuth state token")
    return payload


def _get_secret_cipher() -> Fernet:
    settings = get_settings()
    key = urlsafe_b64encode(sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret_value(value: str) -> str:
    return _get_secret_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret_value(value: str) -> str:
    return _get_secret_cipher().decrypt(value.encode("utf-8")).decode("utf-8")
