from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    ConventionInventoryStage,
    ConventionSession,
    IntakeStagingRecord,
    MobileDevice,
    MobileOpsDiagnostic,
    MobileOpsEvent,
    MobileOpsMetric,
    MobileOpsSnapshot,
    MobileSession,
    OfflineInventoryRecord,
    OfflineSyncConflict,
    OfflineSyncContract,
    OfflineSyncQueue,
    QuickSale,
    QuickSalePayment,
    ScanCapture,
    User,
)
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _user_id(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email)).one()
    assert user.id is not None
    return int(user.id)


def _seed_mobile_ops_rows(session: Session, *, organization_id: int, owner_user_id: int) -> None:
    active_device = MobileDevice(
        organization_id=organization_id,
        device_identifier="ops-device-active",
        device_name="Ops Device Active",
        device_type="tablet",
        device_status="active",
    )
    inactive_device = MobileDevice(
        organization_id=organization_id,
        device_identifier="ops-device-inactive",
        device_name="Ops Device Inactive",
        device_type="scanner",
        device_status="inactive",
    )
    session.add(active_device)
    session.add(inactive_device)
    session.flush()

    active_session = MobileSession(
        organization_id=organization_id,
        device_id=int(active_device.id or 0),
        user_id=owner_user_id,
        session_status="active",
    )
    contract = OfflineSyncContract(
        organization_id=organization_id,
        contract_type="metadata",
        contract_payload_json={"schema_version": 1},
    )
    offline_record = OfflineInventoryRecord(
        organization_id=organization_id,
        inventory_item_id=None,
        local_record_identifier="ops-record-1",
        record_payload_json={"source": "mobile_ops_test"},
    )
    queue_row = OfflineSyncQueue(
        organization_id=organization_id,
        device_id=int(active_device.id or 0),
        queue_status="pending",
        queue_payload_json={"kind": "sale_sync"},
    )
    conflict_row = OfflineSyncConflict(
        organization_id=organization_id,
        inventory_item_id=None,
        conflict_type="inventory_state_mismatch",
        local_payload_json={"local": True},
        server_payload_json={"server": True},
        conflict_status="open",
    )
    capture = ScanCapture(
        organization_id=organization_id,
        device_id=int(active_device.id or 0),
        scan_type="upc",
        scan_value="012345678905",
        normalized_value="012345678905",
        scan_status="lookup_complete",
    )
    session.add(active_session)
    session.add(contract)
    session.add(offline_record)
    session.add(queue_row)
    session.add(conflict_row)
    session.add(capture)
    session.flush()

    staging = IntakeStagingRecord(
        organization_id=organization_id,
        scan_capture_id=int(capture.id or 0),
        staging_status="pending",
        staging_payload_json={"note": "pending intake"},
    )
    convention_session = ConventionSession(
        organization_id=organization_id,
        session_name="Ops Convention",
        session_status="active",
    )
    session.add(staging)
    session.add(convention_session)
    session.flush()

    staged_inventory = ConventionInventoryStage(
        organization_id=organization_id,
        convention_session_id=int(convention_session.id or 0),
        inventory_item_id=4242,
        stage_status="staged",
    )
    sale_without_payment = QuickSale(
        organization_id=organization_id,
        convention_session_id=int(convention_session.id or 0),
        mobile_device_id=int(active_device.id or 0),
        sale_identifier="ops-sale-1",
        sale_status="completed",
        buyer_label="Walk-up A",
        subtotal_amount=Decimal("10.00"),
        discount_amount=Decimal("1.00"),
        total_amount=Decimal("9.00"),
        currency="USD",
        sale_source="mobile",
        created_by_user_id=owner_user_id,
    )
    sale_with_payment = QuickSale(
        organization_id=organization_id,
        convention_session_id=None,
        mobile_device_id=int(active_device.id or 0),
        sale_identifier="ops-sale-2",
        sale_status="completed",
        buyer_label="Walk-up B",
        subtotal_amount=Decimal("5.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("5.00"),
        currency="USD",
        sale_source="offline",
        created_by_user_id=owner_user_id,
    )
    session.add(staged_inventory)
    session.add(sale_without_payment)
    session.add(sale_with_payment)
    session.flush()

    payment = QuickSalePayment(
        organization_id=organization_id,
        quick_sale_id=int(sale_with_payment.id or 0),
        payment_method="venmo_external",
        payment_status="recorded",
        amount=Decimal("5.00"),
        currency="USD",
        payment_reference="venmo-ops-1",
    )
    session.add(payment)
    session.commit()


def test_mobile_ops_dashboard_generation_and_append_only_lineage(client: TestClient, session: Session) -> None:
    owner_email = "mobile-ops-owner@example.com"
    owner = register_and_login(client, owner_email)
    organization_id = _create_organization(client, owner, slug="mobile-ops-org")
    owner_user_id = _user_id(session, owner_email)
    _seed_mobile_ops_rows(session, organization_id=organization_id, owner_user_id=owner_user_id)

    dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-ops", headers=auth_headers(owner))
    assert dashboard.status_code == 200, dashboard.text
    summary = dashboard.json()["data"]["summary"]
    assert summary["devices"] == {"active": 1, "inactive": 1, "active_sessions": 1}
    assert summary["offline"] == {"records": 1, "contracts": 1, "pending_queue": 1, "open_conflicts": 1}
    assert summary["scanning"] == {"captures": 1, "pending_intake": 1, "approved_intake": 0}
    assert summary["convention"] == {"active_sessions": 1, "staged_inventory": 1, "active_booths": 0}
    assert summary["quick_sales"] == {
        "total_sales": 2,
        "completed_sales": 2,
        "total_amount": "14.00",
        "currency": "USD",
        "recorded_external_payments": 1,
    }

    first_generate = client.post(f"/api/v1/organizations/{organization_id}/mobile-ops/generate", headers=auth_headers(owner))
    second_generate = client.post(f"/api/v1/organizations/{organization_id}/mobile-ops/generate", headers=auth_headers(owner))
    assert first_generate.status_code == 201, first_generate.text
    assert second_generate.status_code == 201, second_generate.text
    second_body = second_generate.json()["data"]
    assert second_body["latest_snapshot"] is not None
    assert second_body["latest_snapshot"]["snapshot_type"] == "full_dashboard_snapshot"

    metrics = client.get(f"/api/v1/organizations/{organization_id}/mobile-ops/metrics?limit=50&offset=0", headers=auth_headers(owner))
    diagnostics = client.get(f"/api/v1/organizations/{organization_id}/mobile-ops/diagnostics?limit=50&offset=0", headers=auth_headers(owner))
    snapshots = client.get(f"/api/v1/organizations/{organization_id}/mobile-ops/snapshots?limit=50&offset=0", headers=auth_headers(owner))
    assert metrics.status_code == 200, metrics.text
    assert diagnostics.status_code == 200, diagnostics.text
    assert snapshots.status_code == 200, snapshots.text

    metric_items = metrics.json()["data"]["items"]
    diagnostic_items = diagnostics.json()["data"]["items"]
    snapshot_items = snapshots.json()["data"]["items"]
    assert [row["metric_key"] for row in metric_items] == [
        "active_mobile_devices",
        "inactive_mobile_devices",
        "active_mobile_sessions",
        "offline_inventory_records",
        "pending_sync_queue_items",
        "open_sync_conflicts",
        "scan_captures_count",
        "pending_intake_staging_records",
        "approved_intake_staging_records",
        "active_convention_sessions",
        "staged_convention_inventory",
        "active_booths",
        "quick_sales_count",
        "completed_quick_sales_count",
        "quick_sales_total_amount",
        "recorded_external_payments_count",
    ]
    assert [row["diagnostic_code"] for row in diagnostic_items] == [
        "open_sync_conflicts_present",
        "pending_sync_queue_items_present",
        "pending_intake_records_present",
        "active_convention_without_booth",
        "completed_sales_without_payment_record",
    ]
    assert len(snapshot_items) == 2

    metric_rows = session.exec(select(MobileOpsMetric).where(MobileOpsMetric.organization_id == organization_id)).all()
    diagnostic_rows = session.exec(select(MobileOpsDiagnostic).where(MobileOpsDiagnostic.organization_id == organization_id)).all()
    snapshot_rows = session.exec(select(MobileOpsSnapshot).where(MobileOpsSnapshot.organization_id == organization_id)).all()
    event_rows = session.exec(
        select(MobileOpsEvent)
        .where(MobileOpsEvent.organization_id == organization_id)
        .order_by(MobileOpsEvent.created_at.asc(), MobileOpsEvent.id.asc())
    ).all()
    assert len(metric_rows) == 32
    assert len(diagnostic_rows) == 10
    assert len(snapshot_rows) == 2
    event_types = [row.event_type for row in event_rows]
    assert event_types.count("mobile_ops_metrics_generated") == 2
    assert event_types.count("mobile_ops_diagnostics_generated") == 2
    assert event_types.count("mobile_ops_snapshot_generated") == 2
    assert event_types.count("mobile_ops_diagnostic_created") == 10
    assert event_types.count("mobile_ops_dashboard_accessed") == 3


def test_mobile_ops_org_isolation_and_unauthorized_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "mobile-ops-isolation-owner@example.com")
    outsider = register_and_login(client, "mobile-ops-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="mobile-ops-isolation-org")
    _create_organization(client, outsider, slug="mobile-ops-outsider-org")

    denied_dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-ops", headers=auth_headers(outsider))
    denied_metrics = client.get(f"/api/v1/organizations/{organization_id}/mobile-ops/metrics", headers=auth_headers(outsider))
    denied_generate = client.post(f"/api/v1/organizations/{organization_id}/mobile-ops/generate", headers=auth_headers(outsider))
    assert denied_dashboard.status_code == 403, denied_dashboard.text
    assert denied_metrics.status_code == 403, denied_metrics.text
    assert denied_generate.status_code == 403, denied_generate.text

    attempts = session.exec(
        select(MobileOpsEvent)
        .where(MobileOpsEvent.organization_id == organization_id)
        .where(MobileOpsEvent.event_type == "unauthorized_mobile_ops_access_attempt")
        .order_by(MobileOpsEvent.id.asc())
    ).all()
    assert len(attempts) == 3
