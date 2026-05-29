from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    ConventionInventoryStage,
    ConventionSession,
    IntakeStagingRecord,
    MobileAnalyticsEvent,
    MobileAnalyticsSnapshot,
    MobileDevice,
    MobileDeviceAccessLog,
    MobileDeviceTrustState,
    MobileOpsDiagnostic,
    MobileSession,
    MobileUsageMetric,
    MobileUsageTrend,
    OfflineInventoryRecord,
    OfflineSyncConflict,
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


def _seed_mobile_analytics_rows(session: Session, *, organization_id: int, owner_user_id: int) -> None:
    now = datetime.now(timezone.utc)
    active_device = MobileDevice(
        organization_id=organization_id,
        device_identifier="analytics-device-active",
        device_name="Analytics Active",
        device_type="tablet",
        device_status="active",
        created_at=now,
        last_seen_at=now,
    )
    suspended_device = MobileDevice(
        organization_id=organization_id,
        device_identifier="analytics-device-suspended",
        device_name="Analytics Suspended",
        device_type="scanner",
        device_status="suspended",
        created_at=now,
        last_seen_at=now,
    )
    session.add(active_device)
    session.add(suspended_device)
    session.flush()

    session.add(
        MobileDeviceTrustState(
            organization_id=organization_id,
            mobile_device_id=int(active_device.id or 0),
            trust_status="trusted",
            trust_reason="approved",
            trusted_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        MobileDeviceTrustState(
            organization_id=organization_id,
            mobile_device_id=int(suspended_device.id or 0),
            trust_status="suspended",
            trust_reason="lost",
            suspended_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        MobileSession(
            organization_id=organization_id,
            device_id=int(active_device.id or 0),
            user_id=owner_user_id,
            session_status="active",
            started_at=now,
        )
    )
    session.add(
        OfflineInventoryRecord(
            organization_id=organization_id,
            inventory_item_id=None,
            local_record_identifier="analytics-record-1",
            record_payload_json={"source": "analytics_test"},
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        OfflineSyncQueue(
            organization_id=organization_id,
            device_id=int(active_device.id or 0),
            queue_status="pending",
            queue_payload_json={"kind": "analytics_sync"},
            queued_at=now,
        )
    )
    session.add(
        OfflineSyncConflict(
            organization_id=organization_id,
            inventory_item_id=None,
            conflict_type="inventory_state_mismatch",
            local_payload_json={"local": True},
            server_payload_json={"server": True},
            conflict_status="open",
            created_at=now,
            updated_at=now,
        )
    )
    capture_lookup = ScanCapture(
        organization_id=organization_id,
        device_id=int(active_device.id or 0),
        scan_type="upc",
        scan_value="012345678905",
        normalized_value="012345678905",
        scan_status="lookup_complete",
        created_at=now,
    )
    capture_pending = ScanCapture(
        organization_id=organization_id,
        device_id=int(active_device.id or 0),
        scan_type="upc",
        scan_value="099999999999",
        normalized_value="099999999999",
        scan_status="captured",
        created_at=now,
    )
    session.add(capture_lookup)
    session.add(capture_pending)
    session.flush()

    session.add(
        IntakeStagingRecord(
            organization_id=organization_id,
            scan_capture_id=int(capture_lookup.id or 0),
            staging_status="approved",
            staging_payload_json={"note": "approved"},
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        IntakeStagingRecord(
            organization_id=organization_id,
            scan_capture_id=int(capture_pending.id or 0),
            staging_status="pending",
            staging_payload_json={"note": "pending"},
            created_at=now,
            updated_at=now,
        )
    )

    active_convention = ConventionSession(
        organization_id=organization_id,
        session_name="Analytics Active Convention",
        session_status="active",
        created_at=now,
    )
    planned_convention = ConventionSession(
        organization_id=organization_id,
        session_name="Analytics Planned Convention",
        session_status="planned",
        created_at=now,
    )
    session.add(active_convention)
    session.add(planned_convention)
    session.flush()

    session.add(
        ConventionInventoryStage(
            organization_id=organization_id,
            convention_session_id=int(active_convention.id or 0),
            inventory_item_id=5001,
            stage_status="staged",
            staged_at=now,
        )
    )

    sale_one = QuickSale(
        organization_id=organization_id,
        convention_session_id=int(active_convention.id or 0),
        mobile_device_id=int(active_device.id or 0),
        sale_identifier="analytics-sale-1",
        sale_status="completed",
        buyer_label="Buyer A",
        subtotal_amount=Decimal("10.00"),
        discount_amount=Decimal("1.00"),
        total_amount=Decimal("9.00"),
        currency="USD",
        sale_source="mobile",
        created_by_user_id=owner_user_id,
        created_at=now,
        completed_at=now,
    )
    sale_two = QuickSale(
        organization_id=organization_id,
        convention_session_id=None,
        mobile_device_id=int(active_device.id or 0),
        sale_identifier="analytics-sale-2",
        sale_status="completed",
        buyer_label="Buyer B",
        subtotal_amount=Decimal("5.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("5.00"),
        currency="USD",
        sale_source="offline",
        created_by_user_id=owner_user_id,
        created_at=now,
        completed_at=now,
    )
    sale_three = QuickSale(
        organization_id=organization_id,
        convention_session_id=None,
        mobile_device_id=int(active_device.id or 0),
        sale_identifier="analytics-sale-3",
        sale_status="voided",
        buyer_label="Buyer C",
        subtotal_amount=Decimal("7.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("7.00"),
        currency="USD",
        sale_source="mobile",
        created_by_user_id=owner_user_id,
        created_at=now,
        voided_at=now,
    )
    session.add(sale_one)
    session.add(sale_two)
    session.add(sale_three)
    session.flush()

    session.add(
        QuickSalePayment(
            organization_id=organization_id,
            quick_sale_id=int(sale_two.id or 0),
            payment_method="venmo_external",
            payment_status="recorded",
            amount=Decimal("5.00"),
            currency="USD",
            payment_reference="analytics-venmo-1",
            created_at=now,
        )
    )
    session.add(
        MobileDeviceAccessLog(
            organization_id=organization_id,
            mobile_device_id=int(active_device.id or 0),
            user_id=owner_user_id,
            access_result="allowed",
            access_reason="access_allowed",
            accessed_at=now,
        )
    )
    session.add(
        MobileDeviceAccessLog(
            organization_id=organization_id,
            mobile_device_id=int(suspended_device.id or 0),
            user_id=owner_user_id,
            access_result="denied",
            access_reason="device_suspended",
            accessed_at=now,
        )
    )
    session.add(
        MobileOpsDiagnostic(
            organization_id=organization_id,
            diagnostic_category="offline",
            diagnostic_status="warning",
            diagnostic_code="open_sync_conflicts_present",
            diagnostic_message="Open sync conflicts are present.",
            diagnostic_payload_json={"count": 1},
            created_at=now,
        )
    )
    session.add(
        MobileOpsDiagnostic(
            organization_id=organization_id,
            diagnostic_category="security",
            diagnostic_status="error",
            diagnostic_code="denied_device_access_attempts_present",
            diagnostic_message="Denied device access attempts are present.",
            diagnostic_payload_json={"count": 1},
            created_at=now,
        )
    )
    session.commit()


def test_mobile_analytics_generation_and_lineage(client: TestClient, session: Session) -> None:
    owner_email = "mobile-analytics-owner@example.com"
    owner = register_and_login(client, owner_email)
    organization_id = _create_organization(client, owner, slug="mobile-analytics-org")
    owner_user_id = _user_id(session, owner_email)
    _seed_mobile_analytics_rows(session, organization_id=organization_id, owner_user_id=owner_user_id)

    dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-analytics", headers=auth_headers(owner))
    assert dashboard.status_code == 200, dashboard.text
    summary = dashboard.json()["data"]["summary"]
    assert summary["devices"] == {"registered": 2, "active": 1, "suspended": 1, "active_sessions": 1}
    assert summary["offline"] == {"records_created": 1, "queued_sync_operations": 1, "open_sync_conflicts": 1}
    assert summary["scanning"] == {
        "scans_captured": 2,
        "successful_lookup_rate": "50.00",
        "staged_intake_records": 2,
        "approved_intake_records": 1,
    }
    assert summary["convention"] == {"sessions_created": 2, "active_sessions": 1, "inventory_items_staged": 1}
    assert summary["quick_sales"] == {
        "sales_created": 3,
        "completed_sales": 2,
        "total_amount": "14.00",
        "currency": "USD",
        "average_sale_value": "7.00",
        "recorded_external_payments": 1,
    }
    assert summary["security"] == {"denied_mobile_access_attempts": 1, "suspended_device_count": 1}
    assert summary["performance"] == {
        "lookup_success_rate": "50.00",
        "average_quick_sale_value": "7.00",
        "mobile_ops_warning_count": 1,
        "mobile_ops_error_count": 1,
    }

    first_generate = client.post(f"/api/v1/organizations/{organization_id}/mobile-analytics/generate", headers=auth_headers(owner))
    second_generate = client.post(f"/api/v1/organizations/{organization_id}/mobile-analytics/generate", headers=auth_headers(owner))
    assert first_generate.status_code == 201, first_generate.text
    assert second_generate.status_code == 201, second_generate.text
    assert second_generate.json()["data"]["latest_snapshot"]["snapshot_type"] == "full_analytics_snapshot"

    metrics = client.get(f"/api/v1/organizations/{organization_id}/mobile-analytics/metrics?limit=50&offset=0", headers=auth_headers(owner))
    trends = client.get(f"/api/v1/organizations/{organization_id}/mobile-analytics/trends?limit=50&offset=0", headers=auth_headers(owner))
    snapshots = client.get(f"/api/v1/organizations/{organization_id}/mobile-analytics/snapshots?limit=50&offset=0", headers=auth_headers(owner))
    assert metrics.status_code == 200, metrics.text
    assert trends.status_code == 200, trends.text
    assert snapshots.status_code == 200, snapshots.text

    metric_items = metrics.json()["data"]["items"]
    trend_items = trends.json()["data"]["items"]
    snapshot_items = snapshots.json()["data"]["items"]
    assert [row["metric_key"] for row in metric_items] == [
        "registered_devices",
        "active_devices",
        "suspended_devices",
        "active_sessions",
        "offline_records_created",
        "queued_sync_operations",
        "open_sync_conflicts",
        "scans_captured",
        "successful_lookup_rate",
        "staged_intake_records",
        "approved_intake_records",
        "convention_sessions_created",
        "active_convention_sessions",
        "inventory_items_staged",
        "quick_sales_created",
        "completed_quick_sales",
        "quick_sales_total_amount",
        "average_quick_sale_value",
        "denied_mobile_access_attempts",
        "suspended_device_count",
    ]
    assert [row["trend_key"] for row in trend_items] == [
        "device_activity",
        "offline_activity",
        "scanning_activity",
        "convention_activity",
        "quick_sale_activity",
        "security_activity",
    ]
    assert len(snapshot_items) == 2

    metric_rows = session.exec(select(MobileUsageMetric).where(MobileUsageMetric.organization_id == organization_id)).all()
    trend_rows = session.exec(select(MobileUsageTrend).where(MobileUsageTrend.organization_id == organization_id)).all()
    snapshot_rows = session.exec(select(MobileAnalyticsSnapshot).where(MobileAnalyticsSnapshot.organization_id == organization_id)).all()
    event_rows = session.exec(
        select(MobileAnalyticsEvent)
        .where(MobileAnalyticsEvent.organization_id == organization_id)
        .order_by(MobileAnalyticsEvent.created_at.asc(), MobileAnalyticsEvent.id.asc())
    ).all()
    assert len(metric_rows) == 40
    assert len(trend_rows) == 12
    assert len(snapshot_rows) == 2
    event_types = [row.event_type for row in event_rows]
    assert event_types.count("mobile_metrics_generated") == 2
    assert event_types.count("mobile_trends_generated") == 2
    assert event_types.count("mobile_performance_calculated") == 2
    assert event_types.count("mobile_snapshot_generated") == 2
    assert event_types.count("mobile_analytics_generated") == 2


def test_mobile_analytics_org_isolation_and_unauthorized_denial(client: TestClient, session: Session) -> None:
    owner_email = "mobile-analytics-isolation-owner@example.com"
    outsider_email = "mobile-analytics-isolation-outsider@example.com"
    owner = register_and_login(client, owner_email)
    outsider = register_and_login(client, outsider_email)
    organization_id = _create_organization(client, owner, slug="mobile-analytics-isolation-org")
    _create_organization(client, outsider, slug="mobile-analytics-outsider-org")
    owner_user_id = _user_id(session, owner_email)
    _seed_mobile_analytics_rows(session, organization_id=organization_id, owner_user_id=owner_user_id)

    denied_dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-analytics", headers=auth_headers(outsider))
    denied_generate = client.post(f"/api/v1/organizations/{organization_id}/mobile-analytics/generate", headers=auth_headers(outsider))
    assert denied_dashboard.status_code == 403, denied_dashboard.text
    assert denied_generate.status_code == 403, denied_generate.text

    attempts = session.exec(
        select(MobileAnalyticsEvent)
        .where(MobileAnalyticsEvent.organization_id == organization_id)
        .where(MobileAnalyticsEvent.event_type == "unauthorized_mobile_analytics_access_attempt")
        .order_by(MobileAnalyticsEvent.created_at.asc(), MobileAnalyticsEvent.id.asc())
    ).all()
    assert len(attempts) == 2
