from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    ConventionActivity,
    ConventionModeEvent,
    InventoryCopy,
    MobileAnalyticsEvent,
    MobileAnalyticsSnapshot,
    MobileDeviceAccessLog,
    MobileDeviceSecurityEvent,
    MobileFoundationEvent,
    MobileOpsDiagnostic,
    MobileOpsEvent,
    MobileUsageMetric,
    OfflineInventoryEvent,
    QuickSaleEvent,
    ScanEvent,
    User,
)
from app.schemas.offline_inventory import OfflineSyncConflictRegisterRequest
from app.services.convention_mode_service import remove_inventory
from app.services.offline_inventory_service import register_sync_conflict
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _register_device(client: TestClient, token: str, organization_id: int, *, device_identifier: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/devices",
        headers=auth_headers(token),
        json={
            "device_identifier": device_identifier,
            "device_name": device_identifier,
            "device_type": "tablet",
        },
    )
    assert response.status_code in {200, 201}, response.text
    return int(response.json()["data"]["id"])


def _user_id(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email)).one()
    assert user.id is not None
    return int(user.id)


def _inventory_copy_id(client: TestClient, session: Session, email: str, token: str) -> int:
    create_order(
        client,
        token,
        items=[
            {
                "title": "P44 Regression Item",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 11.00,
            }
        ],
    )
    user_id = _user_id(session, email)
    row = session.exec(
        select(InventoryCopy)
        .where(InventoryCopy.user_id == user_id)
        .order_by(InventoryCopy.id.desc())
    ).first()
    assert row is not None and row.id is not None
    return int(row.id)


def _assign_inventory(session: Session, *, organization_id: int, user_id: int, inventory_item_id: int) -> None:
    from app.models import OrganizationInventoryAssignment

    session.add(
        OrganizationInventoryAssignment(
            organization_id=organization_id,
            inventory_item_id=inventory_item_id,
            assigned_user_id=user_id,
            assigned_by_user_id=user_id,
            assignment_status="ACTIVE",
        )
    )
    session.commit()


def _assert_sorted_ids(rows: list[dict]) -> None:
    ids = [int(row["id"]) for row in rows]
    assert ids == sorted(ids)


def _assert_sorted_payload_keys(payload: dict) -> None:
    assert list(payload.keys()) == sorted(payload.keys())


def test_p44_regression_cross_system_determinism_and_replay_safety(client: TestClient, session: Session) -> None:
    owner_email = "p44-regression-owner@example.com"
    owner = register_and_login(client, owner_email)
    organization_id = _create_organization(client, owner, slug="p44-regression-org")
    owner_user_id = _user_id(session, owner_email)

    alpha_device_id = _register_device(client, owner, organization_id, device_identifier="p44-alpha-device")
    beta_device_id = _register_device(client, owner, organization_id, device_identifier="p44-beta-device")

    trusted = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states",
        headers=auth_headers(owner),
        json={"mobile_device_id": alpha_device_id, "trust_status": "trusted", "trust_reason": "approved"},
    )
    assert trusted.status_code == 201, trusted.text
    trust_state_id = trusted.json()["data"]["id"]

    contract = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/contracts",
        headers=auth_headers(owner),
        json={"contract_type": "metadata", "contract_payload_json": {"schema_version": 1}},
    )
    assert contract.status_code == 201, contract.text

    session_create = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(owner),
        json={"device_id": alpha_device_id},
    )
    assert session_create.status_code == 201, session_create.text

    record_alpha = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory",
        headers=auth_headers(owner),
        json={"local_record_identifier": "p44-record-alpha", "record_payload_json": {"sku": "A"}},
    )
    record_zeta = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory",
        headers=auth_headers(owner),
        json={"local_record_identifier": "p44-record-zeta", "record_payload_json": {"sku": "Z"}},
    )
    assert record_alpha.status_code == 201, record_alpha.text
    assert record_zeta.status_code == 201, record_zeta.text

    change = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory/change",
        headers=auth_headers(owner),
        json={"device_id": alpha_device_id, "change_type": "update", "change_payload_json": {"qty": 2}},
    )
    queue = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory/queue",
        headers=auth_headers(owner),
        json={"device_id": alpha_device_id, "queue_payload_json": {"operation": "push_inventory"}},
    )
    assert change.status_code == 201, change.text
    assert queue.status_code == 201, queue.text

    conflict = register_sync_conflict(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        payload=OfflineSyncConflictRegisterRequest(
            conflict_type="payload_mismatch",
            local_payload_json={"qty": 2},
            server_payload_json={"qty": 5},
        ),
    )
    ack = client.patch(
        f"/api/v1/organizations/{organization_id}/offline-inventory/conflicts/{conflict.id}",
        headers=auth_headers(owner),
        json={"conflict_status": "acknowledged"},
    )
    assert ack.status_code == 200, ack.text

    capture_alpha = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": alpha_device_id, "scan_type": "upc", "scan_value": "012345678905"},
    )
    assert capture_alpha.status_code == 201, capture_alpha.text
    capture_alpha_id = capture_alpha.json()["data"]["capture"]["id"]
    staging = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/staging",
        headers=auth_headers(owner),
        json={"scan_capture_id": capture_alpha_id, "staging_payload_json": {"note": "intake"}},
    )
    assert staging.status_code == 201, staging.text
    staging_id = staging.json()["data"]["id"]
    approved = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/staging/{staging_id}",
        headers=auth_headers(owner),
        json={"staging_status": "approved"},
    )
    assert approved.status_code == 200, approved.text
    capture_zeta = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": alpha_device_id, "scan_type": "qr", "scan_value": "P44-QR-002"},
    )
    assert capture_zeta.status_code == 201, capture_zeta.text

    session_alpha = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions",
        headers=auth_headers(owner),
        json={"session_name": "Alpha Con"},
    )
    session_zeta = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions",
        headers=auth_headers(owner),
        json={"session_name": "Zeta Con"},
    )
    assert session_alpha.status_code == 201, session_alpha.text
    assert session_zeta.status_code == 201, session_zeta.text
    convention_session_id = session_alpha.json()["data"]["id"]
    started = client.patch(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions/{convention_session_id}",
        headers=auth_headers(owner),
        json={"session_status": "active"},
    )
    assert started.status_code == 200, started.text
    booth = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/booths",
        headers=auth_headers(owner),
        json={"convention_session_id": convention_session_id, "booth_name": "Main"},
    )
    assert booth.status_code == 201, booth.text
    booth_id = booth.json()["data"]["id"]
    opened = client.patch(
        f"/api/v1/organizations/{organization_id}/convention-mode/booths/{booth_id}",
        headers=auth_headers(owner),
        json={"booth_status": "active"},
    )
    assert opened.status_code == 200, opened.text
    staged = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/inventory",
        headers=auth_headers(owner),
        json={"convention_session_id": convention_session_id, "inventory_item_id": 42},
    )
    assert staged.status_code == 201, staged.text
    stage_id = staged.json()["data"]["id"]
    remove_inventory(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        stage_id=stage_id,
    )

    inventory_item_id = _inventory_copy_id(client, session, owner_email, owner)
    _assign_inventory(session, organization_id=organization_id, user_id=owner_user_id, inventory_item_id=inventory_item_id)

    sale_alpha = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={
            "sale_identifier": "sale-alpha",
            "sale_source": "offline",
            "currency": "USD",
            "mobile_device_id": alpha_device_id,
        },
    )
    sale_zeta = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={"sale_identifier": "sale-zeta", "sale_source": "convention", "currency": "USD"},
    )
    assert sale_alpha.status_code == 201, sale_alpha.text
    assert sale_zeta.status_code == 201, sale_zeta.text
    sale_id = sale_alpha.json()["data"]["sale"]["id"]
    line_item = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/line-items",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "quantity": 1, "unit_price": "10.00", "discount_amount": "1.00"},
    )
    payment = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/payments",
        headers=auth_headers(owner),
        json={"payment_method": "cash", "amount": "9.00", "currency": "USD"},
    )
    completed = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales/{sale_id}/complete",
        headers=auth_headers(owner),
    )
    assert line_item.status_code == 201, line_item.text
    assert payment.status_code == 201, payment.text
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["sale"]["total_amount"] == "9.00"

    policy = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/policies",
        headers=auth_headers(owner),
        json={"policy_key": "require_trusted_device", "policy_status": "active", "policy_payload_json": {}},
    )
    assert policy.status_code == 201, policy.text
    suspended = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states/{trust_state_id}",
        headers=auth_headers(owner),
        json={"trust_status": "suspended", "trust_reason": "lost device"},
    )
    assert suspended.status_code == 200, suspended.text
    denied_capture = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": alpha_device_id, "scan_type": "upc", "scan_value": "012345678905"},
    )
    assert denied_capture.status_code == 403, denied_capture.text
    unsuspended = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states/{trust_state_id}",
        headers=auth_headers(owner),
        json={"trust_status": "trusted", "trust_reason": "device recovered"},
    )
    assert unsuspended.status_code == 200, unsuspended.text
    resumed_session = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(owner),
        json={"device_id": alpha_device_id},
    )
    assert resumed_session.status_code == 201, resumed_session.text

    first_ops = client.post(f"/api/v1/organizations/{organization_id}/mobile-ops/generate", headers=auth_headers(owner))
    second_ops = client.post(f"/api/v1/organizations/{organization_id}/mobile-ops/generate", headers=auth_headers(owner))
    first_analytics = client.post(f"/api/v1/organizations/{organization_id}/mobile-analytics/generate", headers=auth_headers(owner))
    second_analytics = client.post(f"/api/v1/organizations/{organization_id}/mobile-analytics/generate", headers=auth_headers(owner))
    assert first_ops.status_code == 201, first_ops.text
    assert second_ops.status_code == 201, second_ops.text
    assert first_analytics.status_code == 201, first_analytics.text
    assert second_analytics.status_code == 201, second_analytics.text

    devices = client.get(f"/api/v1/organizations/{organization_id}/mobile/devices?limit=20&offset=0", headers=auth_headers(owner))
    sessions = client.get(f"/api/v1/organizations/{organization_id}/mobile/sessions?limit=20&offset=0", headers=auth_headers(owner))
    offline_dashboard = client.get(f"/api/v1/organizations/{organization_id}/offline-inventory", headers=auth_headers(owner))
    scans = client.get(f"/api/v1/organizations/{organization_id}/mobile-scanning/scans?limit=20&offset=0", headers=auth_headers(owner))
    convention_sessions = client.get(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    quick_sales = client.get(f"/api/v1/organizations/{organization_id}/quick-sales?limit=20&offset=0", headers=auth_headers(owner))
    access_logs = client.get(
        f"/api/v1/organizations/{organization_id}/mobile-security/access-logs?limit=50&offset=0",
        headers=auth_headers(owner),
    )
    ops_metrics = client.get(f"/api/v1/organizations/{organization_id}/mobile-ops/metrics?limit=50&offset=0", headers=auth_headers(owner))
    analytics_snapshots = client.get(
        f"/api/v1/organizations/{organization_id}/mobile-analytics/snapshots?limit=50&offset=0",
        headers=auth_headers(owner),
    )
    analytics_dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-analytics", headers=auth_headers(owner))

    assert devices.status_code == 200, devices.text
    assert sessions.status_code == 200, sessions.text
    assert offline_dashboard.status_code == 200, offline_dashboard.text
    assert scans.status_code == 200, scans.text
    assert convention_sessions.status_code == 200, convention_sessions.text
    assert quick_sales.status_code == 200, quick_sales.text
    assert access_logs.status_code == 200, access_logs.text
    assert ops_metrics.status_code == 200, ops_metrics.text
    assert analytics_snapshots.status_code == 200, analytics_snapshots.text
    assert analytics_dashboard.status_code == 200, analytics_dashboard.text

    assert [row["device_identifier"] for row in devices.json()["data"]["items"]] == ["p44-alpha-device", "p44-beta-device"]
    assert [row["session_status"] for row in sessions.json()["data"]["items"]] == ["terminated", "active"]
    assert [row["local_record_identifier"] for row in offline_dashboard.json()["data"]["recent_records"]] == [
        "p44-record-alpha",
        "p44-record-zeta",
    ]
    assert [row["normalized_value"] for row in scans.json()["data"]["items"]] == ["012345678905", "P44-QR-002"]
    assert [row["session_name"] for row in convention_sessions.json()["data"]["items"]] == ["Alpha Con", "Zeta Con"]
    assert [row["sale_identifier"] for row in quick_sales.json()["data"]["items"]] == ["sale-alpha", "sale-zeta"]
    _assert_sorted_ids(access_logs.json()["data"]["items"])
    assert [row["metric_key"] for row in ops_metrics.json()["data"]["items"]][:4] == [
        "active_mobile_devices",
        "inactive_mobile_devices",
        "active_mobile_sessions",
        "offline_inventory_records",
    ]
    assert len(analytics_snapshots.json()["data"]["items"]) == 2

    analytics_summary = analytics_dashboard.json()["data"]["summary"]
    assert analytics_summary["quick_sales"]["total_amount"] == "9.00"
    assert analytics_summary["security"]["denied_mobile_access_attempts"] >= 1
    assert analytics_summary["performance"]["lookup_success_rate"] == "100.00"

    foundation_events = session.exec(
        select(MobileFoundationEvent)
        .where(MobileFoundationEvent.organization_id == organization_id)
        .order_by(MobileFoundationEvent.created_at.asc(), MobileFoundationEvent.id.asc())
    ).all()
    offline_events = session.exec(
        select(OfflineInventoryEvent)
        .where(OfflineInventoryEvent.organization_id == organization_id)
        .order_by(OfflineInventoryEvent.created_at.asc(), OfflineInventoryEvent.id.asc())
    ).all()
    scan_events = session.exec(
        select(ScanEvent)
        .where(ScanEvent.organization_id == organization_id)
        .order_by(ScanEvent.created_at.asc(), ScanEvent.id.asc())
    ).all()
    convention_events = session.exec(
        select(ConventionModeEvent)
        .where(ConventionModeEvent.organization_id == organization_id)
        .order_by(ConventionModeEvent.created_at.asc(), ConventionModeEvent.id.asc())
    ).all()
    convention_activities = session.exec(
        select(ConventionActivity)
        .where(ConventionActivity.organization_id == organization_id)
        .order_by(ConventionActivity.created_at.asc(), ConventionActivity.id.asc())
    ).all()
    quick_sale_events = session.exec(
        select(QuickSaleEvent)
        .where(QuickSaleEvent.organization_id == organization_id)
        .where(QuickSaleEvent.quick_sale_id == sale_id)
        .order_by(QuickSaleEvent.created_at.asc(), QuickSaleEvent.id.asc())
    ).all()
    security_events = session.exec(
        select(MobileDeviceSecurityEvent)
        .where(MobileDeviceSecurityEvent.organization_id == organization_id)
        .order_by(MobileDeviceSecurityEvent.created_at.asc(), MobileDeviceSecurityEvent.id.asc())
    ).all()
    ops_events = session.exec(
        select(MobileOpsEvent)
        .where(MobileOpsEvent.organization_id == organization_id)
        .order_by(MobileOpsEvent.created_at.asc(), MobileOpsEvent.id.asc())
    ).all()
    analytics_events = session.exec(
        select(MobileAnalyticsEvent)
        .where(MobileAnalyticsEvent.organization_id == organization_id)
        .order_by(MobileAnalyticsEvent.created_at.asc(), MobileAnalyticsEvent.id.asc())
    ).all()
    analytics_metric_rows = session.exec(
        select(MobileUsageMetric)
        .where(MobileUsageMetric.organization_id == organization_id)
        .order_by(MobileUsageMetric.generated_at.asc(), MobileUsageMetric.id.asc())
    ).all()
    analytics_snapshot_rows = session.exec(
        select(MobileAnalyticsSnapshot)
        .where(MobileAnalyticsSnapshot.organization_id == organization_id)
        .order_by(MobileAnalyticsSnapshot.generated_at.desc(), MobileAnalyticsSnapshot.id.desc())
    ).all()

    assert [row.event_type for row in foundation_events] == [
        "mobile_device_registered",
        "mobile_device_registered",
        "offline_contract_created",
        "mobile_session_started",
        "mobile_session_started",
    ]
    assert [row.event_type for row in offline_events] == [
        "offline_inventory_created",
        "offline_inventory_created",
        "offline_change_registered",
        "sync_queue_item_created",
        "sync_conflict_detected",
        "sync_conflict_acknowledged",
    ]
    assert [row.event_type for row in scan_events] == [
        "scan_captured",
        "scan_normalized",
        "inventory_lookup_completed",
        "intake_record_created",
        "intake_record_approved",
        "scan_captured",
        "scan_normalized",
        "inventory_lookup_completed",
    ]
    assert [row.event_type for row in convention_events] == [
        "convention_session_created",
        "convention_session_created",
        "convention_session_started",
        "booth_created",
        "booth_opened",
        "inventory_staged",
        "inventory_removed",
    ]
    assert [row.activity_type for row in convention_activities] == [
        "session_created",
        "session_created",
        "booth_opened",
        "inventory_staged",
        "inventory_removed",
    ]
    assert [row.event_type for row in quick_sale_events] == [
        "quick_sale_created",
        "quick_sale_inventory_reserved",
        "quick_sale_line_item_added",
        "quick_sale_payment_recorded",
        "quick_sale_inventory_sold",
        "quick_sale_completed",
        "quick_sale_offline_queued",
    ]
    security_event_types = [row.event_type for row in security_events]
    assert security_event_types.count("device_trust_state_set") == 1
    assert security_event_types.count("device_security_policy_created") == 1
    assert security_event_types.count("device_suspended") == 1
    assert security_event_types.count("device_unsuspended") == 1
    assert security_event_types.count("device_access_denied") >= 1
    assert security_event_types.count("device_access_allowed") >= 1
    ops_event_types = [row.event_type for row in ops_events]
    assert ops_event_types.count("mobile_ops_metrics_generated") == 2
    assert ops_event_types.count("mobile_ops_diagnostics_generated") == 2
    assert ops_event_types.count("mobile_ops_snapshot_generated") == 2
    analytics_event_types = [row.event_type for row in analytics_events]
    assert analytics_event_types.count("mobile_metrics_generated") == 2
    assert analytics_event_types.count("mobile_trends_generated") == 2
    assert analytics_event_types.count("mobile_snapshot_generated") == 2
    assert analytics_event_types.count("mobile_performance_calculated") == 2
    assert analytics_event_types.count("mobile_analytics_generated") == 2
    assert len(analytics_metric_rows) == 40
    assert len(analytics_snapshot_rows) == 2

    for event_row in [quick_sale_events[0], security_events[0], analytics_events[-1]]:
        _assert_sorted_payload_keys(dict(event_row.event_payload_json or {}))

    for snapshot_row in analytics_snapshot_rows:
        _assert_sorted_payload_keys(dict(snapshot_row.snapshot_payload_json or {}))


def test_p44_regression_org_isolation_and_deny_by_default(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "p44-isolation-owner@example.com")
    outsider = register_and_login(client, "p44-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="p44-isolation-org")
    _create_organization(client, outsider, slug="p44-isolation-outsider-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="p44-owner-device")

    sale = client.post(
        f"/api/v1/organizations/{organization_id}/quick-sales",
        headers=auth_headers(owner),
        json={"sale_identifier": "iso-sale", "sale_source": "convention", "currency": "USD"},
    )
    assert sale.status_code == 201, sale.text

    checks = [
        client.get(f"/api/v1/organizations/{organization_id}/mobile", headers=auth_headers(outsider)),
        client.get(f"/api/v1/organizations/{organization_id}/offline-inventory", headers=auth_headers(outsider)),
        client.post(
            f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
            headers=auth_headers(outsider),
            json={"device_id": device_id, "scan_type": "barcode", "scan_value": "123"},
        ),
        client.get(f"/api/v1/organizations/{organization_id}/convention-mode", headers=auth_headers(outsider)),
        client.get(f"/api/v1/organizations/{organization_id}/quick-sales", headers=auth_headers(outsider)),
        client.get(f"/api/v1/organizations/{organization_id}/mobile-ops", headers=auth_headers(outsider)),
        client.get(f"/api/v1/organizations/{organization_id}/mobile-security", headers=auth_headers(outsider)),
        client.get(f"/api/v1/organizations/{organization_id}/mobile-analytics", headers=auth_headers(outsider)),
    ]
    assert all(response.status_code == 403 for response in checks)

    assert len(
        session.exec(
            select(MobileFoundationEvent)
            .where(MobileFoundationEvent.organization_id == organization_id)
            .where(MobileFoundationEvent.event_type == "unauthorized_mobile_access_attempt")
        ).all()
    ) >= 1
    assert len(
        session.exec(
            select(OfflineInventoryEvent)
            .where(OfflineInventoryEvent.organization_id == organization_id)
            .where(OfflineInventoryEvent.event_type == "unauthorized_offline_inventory_access_attempt")
        ).all()
    ) >= 1
    assert len(
        session.exec(
            select(ScanEvent)
            .where(ScanEvent.organization_id == organization_id)
            .where(ScanEvent.event_type == "unauthorized_scan_access_attempt")
        ).all()
    ) >= 1
    assert len(
        session.exec(
            select(ConventionModeEvent)
            .where(ConventionModeEvent.organization_id == organization_id)
            .where(ConventionModeEvent.event_type == "unauthorized_convention_access_attempt")
        ).all()
    ) >= 1
    assert len(
        session.exec(
            select(QuickSaleEvent)
            .where(QuickSaleEvent.organization_id == organization_id)
            .where(QuickSaleEvent.event_type == "unauthorized_quick_sale_access_attempt")
        ).all()
    ) >= 1
    assert len(
        session.exec(
            select(MobileOpsEvent)
            .where(MobileOpsEvent.organization_id == organization_id)
            .where(MobileOpsEvent.event_type == "unauthorized_mobile_ops_access_attempt")
        ).all()
    ) >= 1
    assert len(
        session.exec(
            select(MobileDeviceSecurityEvent)
            .where(MobileDeviceSecurityEvent.organization_id == organization_id)
            .where(MobileDeviceSecurityEvent.event_type == "unauthorized_mobile_security_access_attempt")
        ).all()
    ) >= 1
    assert len(
        session.exec(
            select(MobileAnalyticsEvent)
            .where(MobileAnalyticsEvent.organization_id == organization_id)
            .where(MobileAnalyticsEvent.event_type == "unauthorized_mobile_analytics_access_attempt")
        ).all()
    ) >= 1


def test_p44_regression_internal_only_source_guards() -> None:
    root = Path(__file__).resolve().parents[3]
    p44_files = [
        root / "apps/api/app/api/mobile_foundation.py",
        root / "apps/api/app/api/offline_inventory.py",
        root / "apps/api/app/api/mobile_scanning.py",
        root / "apps/api/app/api/convention_mode.py",
        root / "apps/api/app/api/quick_sales.py",
        root / "apps/api/app/api/mobile_ops_dashboard.py",
        root / "apps/api/app/api/mobile_device_security.py",
        root / "apps/api/app/api/mobile_analytics.py",
        root / "apps/api/app/services/mobile_foundation_service.py",
        root / "apps/api/app/services/offline_inventory_service.py",
        root / "apps/api/app/services/mobile_scanning_service.py",
        root / "apps/api/app/services/convention_mode_service.py",
        root / "apps/api/app/services/quick_sale_service.py",
        root / "apps/api/app/services/mobile_ops_dashboard_service.py",
        root / "apps/api/app/services/mobile_device_security_service.py",
        root / "apps/api/app/services/mobile_analytics_service.py",
    ]
    forbidden_tokens = (
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "aiohttp",
        "stripe",
        "paypal",
        "squareup",
        "shippo",
        "easypost",
        "firebase",
        "push notification",
        "native sdk",
        "https://",
        "http://",
    )

    for path in p44_files:
        contents = path.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            assert token not in contents, f"Forbidden external-processing token {token!r} found in {path}"
