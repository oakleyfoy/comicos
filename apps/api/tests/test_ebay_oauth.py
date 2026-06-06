from __future__ import annotations

from urllib.parse import parse_qs

import httpx

from app.core.config import Settings
from app.services.ebay_oauth import (
    EBAY_OAUTH_SCOPE,
    EbayOAuthConfigurationError,
    acquire_ebay_oauth_access_token,
)


def test_acquire_ebay_oauth_access_token_posts_client_credentials_payload() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["authorization"] = request.headers["authorization"]
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "access_token": "access-token-123",
                "token_type": "Bearer",
                "expires_in": 7200,
                "scope": EBAY_OAUTH_SCOPE,
            },
        )

    settings = Settings.model_validate(
        {
            "EBAY_API_CLIENT_ID": "client-id",
            "EBAY_API_CLIENT_SECRET": "client-secret",
            "EBAY_ENVIRONMENT": "production",
        }
    )

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.ebay.com") as client:
        token = acquire_ebay_oauth_access_token(settings=settings, client=client)

    assert token.access_token == "access-token-123"
    assert token.environment == "production"
    assert seen["method"] == "POST"
    assert seen["path"] == "/identity/v1/oauth2/token"
    assert seen["authorization"].startswith("Basic ")
    assert seen["content_type"].startswith("application/x-www-form-urlencoded")
    form = parse_qs(seen["body"])
    assert form["grant_type"] == ["client_credentials"]
    assert form["scope"] == [EBAY_OAUTH_SCOPE]


def test_acquire_ebay_oauth_access_token_requires_client_secret() -> None:
    settings = Settings.model_validate(
        {
            "EBAY_API_CLIENT_ID": "client-id",
            "EBAY_API_CLIENT_SECRET": "",
            "EBAY_ENVIRONMENT": "production",
        }
    )

    try:
        acquire_ebay_oauth_access_token(settings=settings)
    except EbayOAuthConfigurationError as exc:
        assert "EBAY_API_CLIENT_SECRET" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected configuration error when client secret is missing.")
