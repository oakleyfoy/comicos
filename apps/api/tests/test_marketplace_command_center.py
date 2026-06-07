"""P88-05 Marketplace Command Center tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_command_center_api_returns_payload(client: TestClient) -> None:
    token = register_and_login(client, "p88-mcc@example.com")
    with patch(
        "app.services.marketplace.adapters.adapter_registry.get_marketplace_adapter",
        MagicMock(),
    ) as mock_get_adapter:
        resp = client.get("/api/v1/marketplace-command-center", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "kpis" in data
    assert "best_deals_today" in data
    assert "quick_actions" in data
    mock_get_adapter.assert_not_called()


def test_command_center_empty_state(client: TestClient) -> None:
    token = register_and_login(client, "p88-mcc-empty@example.com")
    resp = client.get("/api/v1/marketplace-command-center", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "OK"
    assert "kpis" in data
    assert isinstance(data["best_deals_today"], list)


def test_command_center_does_not_run_live_search(client: TestClient) -> None:
    token = register_and_login(client, "p88-mcc-nosearch@example.com")
    with patch(
        "app.services.marketplace_command_center_service.list_acquisition_opportunities",
    ) as list_opps:
        list_opps.return_value = type(
            "R",
            (),
            {"items": [], "total_items": 0, "limit": 120, "offset": 0},
        )()
        with patch("app.services.marketplace.adapters.ebay_adapter.EbayMarketplaceAdapter.search") as live_search:
            resp = client.get("/api/v1/marketplace-command-center", headers=auth_headers(token))
            assert resp.status_code == 200
            for call in list_opps.call_args_list:
                assert call.kwargs.get("refresh") is False
            live_search.assert_not_called()
