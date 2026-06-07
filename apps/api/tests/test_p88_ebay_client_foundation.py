"""P88 eBay client foundation tests (no Browse search)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.services.ebay_oauth import EbayOAuthAccessToken, EbayOAuthConfigurationError
from app.services.marketplace.ebay_client import (
    EbayBrowseClient,
    get_cached_ebay_access_token,
    load_ebay_configuration,
)


def test_load_ebay_configuration_not_configured() -> None:
    cfg = load_ebay_configuration(Settings(ebay_api_client_id="", ebay_api_client_secret=""))
    assert cfg.configured is False
    assert cfg.client_id_present is False


def test_load_ebay_configuration_configured() -> None:
    cfg = load_ebay_configuration(
        Settings(ebay_api_client_id="id", ebay_api_client_secret="secret", ebay_environment="SANDBOX")
    )
    assert cfg.configured is True
    assert cfg.environment == "sandbox"


def test_token_cache_without_http_when_warm() -> None:
    token = EbayOAuthAccessToken(
        access_token="abc",
        token_type="Bearer",
        expires_in=3600,
        scope="scope",
        environment="production",
    )
    with patch(
        "app.services.marketplace.ebay_client.acquire_ebay_oauth_access_token",
        return_value=token,
    ) as acquire:
        first = get_cached_ebay_access_token(
            settings=Settings(ebay_api_client_id="id", ebay_api_client_secret="secret"),
            force_refresh=True,
        )
        second = get_cached_ebay_access_token(
            settings=Settings(ebay_api_client_id="id", ebay_api_client_secret="secret"),
        )
    assert first.access_token == "abc"
    assert second.access_token == "abc"
    assert acquire.call_count == 1


def test_browse_client_authorization_header() -> None:
    token = EbayOAuthAccessToken(
        access_token="tok",
        token_type="Bearer",
        expires_in=3600,
        scope="scope",
        environment="production",
    )
    with patch("app.services.marketplace.ebay_client.get_cached_ebay_access_token", return_value=token):
        client = EbayBrowseClient(settings=Settings(ebay_api_client_id="id", ebay_api_client_secret="secret"))
        assert client.authorization_header()["Authorization"] == "Bearer tok"

    with pytest.raises(EbayOAuthConfigurationError):
        EbayBrowseClient(settings=Settings(ebay_api_client_id="", ebay_api_client_secret=""))
