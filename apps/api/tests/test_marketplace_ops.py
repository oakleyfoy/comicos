from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.marketplace_ops_registry import (
    list_marketplace_ops_metric_definitions,
)
from test_inventory import auth_headers, register_and_login
import test_marketplace_ops_dashboard as ops_tests


def test_marketplace_ops_dashboard_smoke_and_registry_ordering(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "marketplace-ops-smoke@example.com")
    organization_id = ops_tests._create_organization(client, owner_token, slug="marketplace-ops-smoke")
    account_id = ops_tests._connect_marketplace_account(client, owner_token, organization_id)
    ops_tests._seed_ops_data(
        client,
        session,
        "marketplace-ops-smoke@example.com",
        owner_token,
        organization_id,
        account_id,
    )

    dashboard = client.get(f"/api/v1/organizations/{organization_id}/marketplace-ops", headers=auth_headers(owner_token))
    assert dashboard.status_code == 200, dashboard.text

    diagnostics = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/diagnostics/generate",
        headers=auth_headers(owner_token),
    )
    assert diagnostics.status_code == 201, diagnostics.text
    assert [row["diagnostic_code"] for row in diagnostics.json()["data"]["items"]] == [
        "listing_validation_failures_present",
        "unresolved_sync_conflicts_present",
        "failed_sync_runs_present",
        "transaction_mismatches_present",
        "pending_offer_reviews_present",
        "failed_event_processing_runs_present",
    ]

    snapshot = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/snapshot",
        headers=auth_headers(owner_token),
    )
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.json()["data"]["snapshot_type"] == "full_dashboard_snapshot"

    metrics = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/metrics?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert metrics.status_code == 200, metrics.text
    assert [row["metric_key"] for row in metrics.json()["data"]["items"]] == [
        definition.metric_key for definition in list_marketplace_ops_metric_definitions()
    ]

    metrics_after_snapshot = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/metrics?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert metrics_after_snapshot.status_code == 200, metrics_after_snapshot.text
    assert [row["metric_key"] for row in metrics_after_snapshot.json()["data"]["items"]] == [
        definition.metric_key for definition in list_marketplace_ops_metric_definitions()
    ]

    diagnostics_after_snapshot = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/diagnostics?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert diagnostics_after_snapshot.status_code == 200, diagnostics_after_snapshot.text
    assert [row["diagnostic_code"] for row in diagnostics_after_snapshot.json()["data"]["items"]] == [
        "listing_validation_failures_present",
        "unresolved_sync_conflicts_present",
        "failed_sync_runs_present",
        "transaction_mismatches_present",
        "pending_offer_reviews_present",
        "failed_event_processing_runs_present",
    ]
