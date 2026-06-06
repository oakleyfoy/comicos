from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings

EBAY_OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"
EBAY_OAUTH_BASE_URLS = {
    "production": "https://api.ebay.com",
    "sandbox": "https://api.sandbox.ebay.com",
}


class EbayOAuthError(Exception):
    pass


class EbayOAuthConfigurationError(EbayOAuthError):
    pass


class EbayOAuthAuthenticationError(EbayOAuthError):
    pass


@dataclass(frozen=True)
class EbayOAuthAccessToken:
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    environment: str


def _resolve_environment(settings: Settings) -> str:
    environment = settings.ebay_environment.strip().lower()
    if not environment:
        raise EbayOAuthConfigurationError("EBAY_ENVIRONMENT is not configured.")
    if environment not in EBAY_OAUTH_BASE_URLS:
        raise EbayOAuthConfigurationError(f"Unsupported EBAY_ENVIRONMENT value: {environment}")
    return environment


def _build_basic_auth_header(client_id: str, client_secret: str) -> str:
    token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def acquire_ebay_oauth_access_token(
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> EbayOAuthAccessToken:
    resolved = settings or get_settings()
    client_id = resolved.ebay_api_client_id.strip()
    client_secret = resolved.ebay_api_client_secret.strip()
    if not client_id:
        raise EbayOAuthConfigurationError("EBAY_API_CLIENT_ID is not configured.")
    if not client_secret:
        raise EbayOAuthConfigurationError("EBAY_API_CLIENT_SECRET is not configured.")

    environment = _resolve_environment(resolved)
    base_url = EBAY_OAUTH_BASE_URLS[environment]
    owns_client = client is None
    oauth_client = client or httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)
    try:
        response = oauth_client.post(
            "/identity/v1/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "scope": EBAY_OAUTH_SCOPE,
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": _build_basic_auth_header(client_id, client_secret),
            },
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()
        raise EbayOAuthAuthenticationError(
            f"eBay OAuth token request failed with HTTP {exc.response.status_code}"
            + (f": {detail}" if detail else "")
        ) from exc
    except httpx.HTTPError as exc:
        raise EbayOAuthAuthenticationError("Unable to reach eBay OAuth token endpoint.") from exc
    finally:
        if owns_client:
            oauth_client.close()

    try:
        payload = response.json()
    except ValueError as exc:  # pragma: no cover - defensive
        raise EbayOAuthAuthenticationError("eBay OAuth token endpoint returned invalid JSON.") from exc

    access_token = str(payload.get("access_token") or "").strip()
    token_type = str(payload.get("token_type") or "Bearer").strip()
    scope = str(payload.get("scope") or EBAY_OAUTH_SCOPE).strip()
    expires_in_raw = payload.get("expires_in", 0)
    try:
        expires_in = int(expires_in_raw)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise EbayOAuthAuthenticationError("eBay OAuth token endpoint returned invalid expires_in.") from exc

    if not access_token:
        raise EbayOAuthAuthenticationError("eBay OAuth token endpoint did not return an access token.")

    return EbayOAuthAccessToken(
        access_token=access_token,
        token_type=token_type or "Bearer",
        expires_in=expires_in,
        scope=scope or EBAY_OAUTH_SCOPE,
        environment=environment,
    )
