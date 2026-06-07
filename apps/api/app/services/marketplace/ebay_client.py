"""P88 eBay Browse API client foundation (OAuth config + token cache; no search)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from app.core.config import Settings, get_settings
from app.services.ebay_oauth import (
    EbayOAuthAccessToken,
    EbayOAuthConfigurationError,
    acquire_ebay_oauth_access_token,
)

_TOKEN_CACHE: EbayOAuthAccessToken | None = None
_TOKEN_EXPIRES_AT: float = 0.0
_TOKEN_LOCK = Lock()
_TOKEN_SKEW_SECONDS = 60.0


@dataclass(frozen=True)
class EbayConfigurationStatus:
    configured: bool
    environment: str
    client_id_present: bool
    client_secret_present: bool
    message: str


@dataclass(frozen=True)
class EbayBrowseClientConfig:
    environment: str
    api_base_url: str
    client_id: str
    client_secret: str


def load_ebay_configuration(settings: Settings | None = None) -> EbayConfigurationStatus:
    resolved = settings or get_settings()
    client_id = resolved.ebay_api_client_id.strip()
    client_secret = resolved.ebay_api_client_secret.strip()
    environment = (resolved.ebay_environment or "production").strip().lower() or "production"
    id_ok = bool(client_id)
    secret_ok = bool(client_secret)
    configured = id_ok and secret_ok
    if configured:
        message = f"eBay credentials present ({environment})."
    else:
        missing = []
        if not id_ok:
            missing.append("client id")
        if not secret_ok:
            missing.append("client secret")
        message = f"Missing eBay {' and '.join(missing)}."
    return EbayConfigurationStatus(
        configured=configured,
        environment=environment,
        client_id_present=id_ok,
        client_secret_present=secret_ok,
        message=message,
    )


def _resolve_browse_base_url(environment: str) -> str:
    env = environment.strip().lower()
    if env == "sandbox":
        return "https://api.sandbox.ebay.com"
    return "https://api.ebay.com"


def load_ebay_browse_client_config(settings: Settings | None = None) -> EbayBrowseClientConfig:
    resolved = settings or get_settings()
    status = load_ebay_configuration(resolved)
    if not status.configured:
        raise EbayOAuthConfigurationError(status.message)
    environment = status.environment
    return EbayBrowseClientConfig(
        environment=environment,
        api_base_url=_resolve_browse_base_url(environment),
        client_id=resolved.ebay_api_client_id.strip(),
        client_secret=resolved.ebay_api_client_secret.strip(),
    )


def get_cached_ebay_access_token(*, settings: Settings | None = None, force_refresh: bool = False) -> EbayOAuthAccessToken:
    global _TOKEN_CACHE, _TOKEN_EXPIRES_AT
    now = time.time()
    with _TOKEN_LOCK:
        if (
            not force_refresh
            and _TOKEN_CACHE is not None
            and now < (_TOKEN_EXPIRES_AT - _TOKEN_SKEW_SECONDS)
        ):
            return _TOKEN_CACHE
        token = acquire_ebay_oauth_access_token(settings=settings)
        _TOKEN_CACHE = token
        _TOKEN_EXPIRES_AT = now + max(0, token.expires_in)
        return token


class EbayBrowseClient:
    """Browse API placeholder — search/item calls added in a later phase."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._config = load_ebay_browse_client_config(self._settings)

    @property
    def config(self) -> EbayBrowseClientConfig:
        return self._config

    def authorization_header(self, *, force_refresh: bool = False) -> dict[str, str]:
        token = get_cached_ebay_access_token(settings=self._settings, force_refresh=force_refresh)
        token_type = token.token_type or "Bearer"
        return {"Authorization": f"{token_type} {token.access_token}"}
