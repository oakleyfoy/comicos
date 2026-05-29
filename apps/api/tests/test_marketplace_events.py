from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import MarketplaceEvent, MarketplaceEventLineage, MarketplaceEventProcessingRun
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _connect_marketplace(client: TestClient, token: str, organization_id: int, suffix: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": "ebay",
            "marketplace_account_id": f"ebay-events-{suffix}",
            "display_name": "Events eBay",
            "credential_type": "oauth_token",
            "credential_reference": f"vault://marketplace/ebay-events-{suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def test_event_ingestion_processing_and_deterministic_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-events-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-events-org")
    account_id = _connect_marketplace(client, owner, organization_id, "ordering")

    first = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "external_event_identifier": "evt-order-1",
            "event_type": "order_created",
            "event_payload_json": {"order_id": "1001"},
            "received_at": "2026-05-29T10:00:00Z",
        },
    )
    second = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "external_event_identifier": "evt-order-2",
            "event_type": "order_updated",
            "event_payload_json": {"order_id": "1002"},
            "received_at": "2026-05-29T11:00:00Z",
        },
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    listing = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-events?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert listing.status_code == 200, listing.text
    payload = listing.json()["data"]
    assert [row["external_event_identifier"] for row in payload["items"]] == ["evt-order-2", "evt-order-1"]
    assert payload["summary"]["total_events"] == 2
    assert payload["summary"]["validated_events"] == 2

    processed = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/process",
        headers=auth_headers(owner),
        json={"marketplace_event_id": int(first.json()["data"]["event"]["id"])},
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["data"]["event"]["event_status"] == "processed"
    assert processed.json()["data"]["processing_runs"][0]["processing_status"] == "completed"

    session.expire_all()
    runs = session.exec(
        select(MarketplaceEventProcessingRun)
        .where(MarketplaceEventProcessingRun.organization_id == organization_id)
        .order_by(MarketplaceEventProcessingRun.started_at.asc(), MarketplaceEventProcessingRun.id.asc())
    ).all()
    assert len(runs) == 1
    assert runs[0].processing_status == "completed"
    events = session.exec(
        select(MarketplaceEvent)
        .where(MarketplaceEvent.organization_id == organization_id)
        .order_by(MarketplaceEvent.received_at.asc(), MarketplaceEvent.id.asc())
    ).all()
    assert [row.event_status for row in events] == ["processed", "validated"]


def test_duplicate_event_detection_and_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-events-duplicate@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-events-duplicate-org")
    account_id = _connect_marketplace(client, owner, organization_id, "duplicate")

    first = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "external_event_identifier": "evt-duplicate-1",
            "event_type": "listing_created",
            "event_payload_json": {"listing_id": "l1"},
        },
    )
    duplicate = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "external_event_identifier": "evt-duplicate-1",
            "event_type": "listing_created",
            "event_payload_json": {"listing_id": "l1"},
        },
    )
    assert first.status_code == 201, first.text
    assert duplicate.status_code == 201, duplicate.text
    assert first.json()["data"]["event"]["id"] == duplicate.json()["data"]["event"]["id"]

    session.expire_all()
    events = session.exec(select(MarketplaceEvent).where(MarketplaceEvent.organization_id == organization_id)).all()
    assert len(events) == 1
    lineage = session.exec(
        select(MarketplaceEventLineage)
        .where(MarketplaceEventLineage.organization_id == organization_id)
        .order_by(MarketplaceEventLineage.created_at.asc(), MarketplaceEventLineage.id.asc())
    ).all()
    assert [row.lineage_event_type for row in lineage] == [
        "marketplace_event_ingested",
        "marketplace_duplicate_event_detected",
    ]


def test_validation_failures_and_org_isolation(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-events-validation-owner@example.com")
    outsider = register_and_login(client, "marketplace-events-validation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-events-validation-org")
    _create_organization(client, outsider, slug="marketplace-events-validation-outsider-org")
    account_id = _connect_marketplace(client, owner, organization_id, "validation")

    failed = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "external_event_identifier": "evt-invalid-1",
            "event_type": "not_a_real_event",
            "event_payload_json": {"unexpected": True},
        },
    )
    assert failed.status_code == 201, failed.text
    assert failed.json()["data"]["event"]["event_status"] == "failed"
    assert failed.json()["data"]["validation_errors"][0]["code"] == "event_type_invalid"

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-events",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    session.expire_all()
    failed_events = session.exec(
        select(MarketplaceEvent)
        .where(MarketplaceEvent.organization_id == organization_id)
        .where(MarketplaceEvent.event_status == "failed")
    ).all()
    assert len(failed_events) == 1
    lineage = session.exec(
        select(MarketplaceEventLineage)
        .where(MarketplaceEventLineage.organization_id == organization_id)
        .where(MarketplaceEventLineage.lineage_event_type == "unauthorized_marketplace_event_access_attempt")
    ).all()
    assert lineage
