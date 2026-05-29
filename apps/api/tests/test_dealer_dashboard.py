from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    OrganizationDealerDashboardEvent,
    OrganizationDealerDashboardSnapshot,
    OrganizationDealerOperationalMetric,
)
from app.schemas.organization_dealer_dashboard import LINEAGE_DASHBOARD_PREFIX
from app.services.dealer_dashboard_service import (
    _require_dashboard_access,
    generate_dashboard_snapshot,
    generate_operational_metrics,
)
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _inventory_copy_id(client: TestClient, token: str) -> int:
    create_order(client, token)
    listing = client.get("/inventory?page=1&page_size=1", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    return int(listing.json()["items"][0]["inventory_copy_id"])


def _invite_staff(client: TestClient, owner: str, organization_id: int, email: str) -> tuple[str, int]:
    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": email},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["data"]["invitation_token"]
    staff = register_and_login(client, email)
    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(staff))
    assert accepted.status_code == 200, accepted.text
    return staff, int(accepted.json()["data"]["user_id"])


def test_dashboard_snapshot_and_metric_generation(client: TestClient) -> None:
    owner = register_and_login(client, "dash-owner@example.com")
    organization_id = _create_organization(client, owner, slug="dash-org")
    staff, staff_user_id = _invite_staff(client, owner, organization_id, "dash-staff@example.com")
    inventory_item_id = _inventory_copy_id(client, owner)

    assigned = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/assign",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )
    assert assigned.status_code in {200, 201}, assigned.text

    dashboard = client.get(
        f"/api/v1/organizations/{organization_id}/dashboard?refresh=true",
        headers=auth_headers(owner),
    )
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()["data"]
    assert data["organization_id"] == organization_id
    assert len(data["sections"]) >= 6
    section_keys = [row["section_key"] for row in data["sections"]]
    assert section_keys == ["inventory", "reviews", "activity", "storefront", "notifications", "security"]
    inventory_section = next(row for row in data["sections"] if row["section_key"] == "inventory")
    assert inventory_section["metrics"]["active_inventory_count"] >= 1
    assert inventory_section["metrics"]["active_staff_count"] >= 2

    metrics = client.get(
        f"/api/v1/organizations/{organization_id}/dashboard/metrics?limit=50&offset=0",
        headers=auth_headers(owner),
    )
    assert metrics.status_code == 200, metrics.text
    metric_keys = {row["metric_key"] for row in metrics.json()["data"]["items"]}
    assert "assigned_inventory_count" in metric_keys
    assert "pending_reviews_count" in metric_keys
    assigned_row = next(row for row in metrics.json()["data"]["items"] if row["metric_key"] == "assigned_inventory_count")
    assert int(assigned_row["metric_value_json"]["value"]) >= 1


def test_org_isolation_and_unauthorized_dashboard_denial(client: TestClient) -> None:
    owner = register_and_login(client, "dash-isolation-owner@example.com")
    outsider = register_and_login(client, "dash-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="dash-isolation-org")
    other_org_id = _create_organization(client, outsider, slug="dash-isolation-other")
    staff, _staff_user_id = _invite_staff(client, owner, organization_id, "dash-isolation-staff@example.com")

    denied = client.get(f"/api/v1/organizations/{organization_id}/dashboard", headers=auth_headers(staff))
    assert denied.status_code == 403, denied.text

    cross = client.get(f"/api/v1/organizations/{other_org_id}/dashboard", headers=auth_headers(owner))
    assert cross.status_code == 403, cross.text

    owner_view = client.get(f"/api/v1/organizations/{organization_id}/dashboard/snapshots", headers=auth_headers(owner))
    assert owner_view.status_code == 200, owner_view.text
    assert all(row["organization_id"] == organization_id for row in owner_view.json()["data"]["items"])


def test_deterministic_snapshot_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "dash-order-owner@example.com")
    organization_id = _create_organization(client, owner, slug="dash-order-org")

    base_time = datetime(2026, 7, 2, 10, 0, 0, tzinfo=timezone.utc)
    first = generate_dashboard_snapshot(session, organization_id=organization_id)
    first.generated_at = base_time
    session.add(first)
    second = generate_dashboard_snapshot(session, organization_id=organization_id)
    second.generated_at = base_time
    session.add(second)
    session.commit()

    listing = client.get(
        f"/api/v1/organizations/{organization_id}/dashboard/snapshots?limit=10&offset=0",
        headers=auth_headers(owner),
    )
    assert listing.status_code == 200, listing.text
    ids = [row["id"] for row in listing.json()["data"]["items"]]
    assert ids == sorted(ids, reverse=True)


def test_append_only_dashboard_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "dash-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="dash-lineage-org")
    staff, staff_user_id = _invite_staff(client, owner, organization_id, "dash-lineage-staff@example.com")

    generate_operational_metrics(session, organization_id=organization_id)
    generate_dashboard_snapshot(session, organization_id=organization_id)
    session.commit()

    denied = client.get(f"/api/v1/organizations/{organization_id}/dashboard", headers=auth_headers(staff))
    assert denied.status_code == 403, denied.text

    with pytest.raises(HTTPException) as exc:
        _require_dashboard_access(
            session,
            organization_id=organization_id,
            actor_user_id=staff_user_id,
            record_access=False,
        )
    assert exc.value.status_code == 403

    lineage = session.exec(
        select(OrganizationDealerDashboardEvent)
        .where(OrganizationDealerDashboardEvent.organization_id == organization_id)
        .where(OrganizationDealerDashboardEvent.event_type.like(f"{LINEAGE_DASHBOARD_PREFIX}%"))
        .order_by(OrganizationDealerDashboardEvent.id.asc())
    ).all()
    types = [row.event_type for row in lineage]
    assert "lineage.dashboard_metric_generated" in types
    assert "lineage.dashboard_snapshot_generated" in types
    assert "lineage.unauthorized_dashboard_access_attempt" in types

    assert session.exec(select(OrganizationDealerDashboardSnapshot).where(OrganizationDealerDashboardSnapshot.organization_id == organization_id)).all()
    assert session.exec(select(OrganizationDealerOperationalMetric).where(OrganizationDealerOperationalMetric.organization_id == organization_id)).all()
