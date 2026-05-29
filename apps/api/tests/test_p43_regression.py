from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, LiveSaleSession, MarketplaceEvent, MarketplaceListingDraft, MarketplaceOrder, User
from app.services.marketplace_kpi_registry import list_marketplace_kpi_definitions
from app.services.marketplace_ops_registry import list_marketplace_ops_metric_definitions
from app.services.marketplace_trends import list_marketplace_trend_definitions
from test_inventory import auth_headers, register_and_login
import test_live_sales as live_sales_tests
import test_marketplace_accounts as account_tests
import test_marketplace_analytics as analytics_tests
import test_marketplace_events as event_tests
import test_marketplace_inventory_sync as sync_tests
import test_marketplace_listings as listing_tests
import test_marketplace_orders as order_tests
import test_marketplace_pricing as pricing_tests
import test_shopify_sync as shopify_tests


P43_SERVICE_DIR = Path(__file__).resolve().parents[1] / "app" / "services"
P43_EXTERNAL_CLIENT_MARKERS = ("requests.", "httpx.", "aiohttp", "urllib.request")


def _seed_regression_org(client: TestClient, session: Session) -> dict[str, object]:
    owner_email = "p43-regression-owner@example.com"
    owner_token = register_and_login(client, owner_email)
    organization_id = analytics_tests._create_organization(client, owner_token, slug="p43-regression-org")
    ebay_account = account_tests._connect_marketplace(
        client,
        owner_token,
        organization_id,
        marketplace_type="ebay",
        marketplace_account_id="ebay-p43-regression",
        display_name="P43 Regression eBay",
        credential_reference="vault://marketplace/ebay-p43-regression",
    )
    assert ebay_account.status_code == 201, ebay_account.text
    ebay_account_id = int(ebay_account.json()["data"]["account"]["id"])
    shopify_account_id = analytics_tests._connect_marketplace_account(client, owner_token, organization_id)

    analytics_tests._seed_analytics_data(
        client,
        session,
        owner_email,
        owner_token,
        organization_id,
        shopify_account_id,
    )

    session.expire_all()
    user = session.exec(select(User).where(User.email == owner_email)).one()
    inventory_item_ids = [
        int(row.id or 0)
        for row in session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == user.id)
            .order_by(InventoryCopy.id.asc())
            .limit(3)
        ).all()
    ]
    listing_ids = [
        int(row.id or 0)
        for row in session.exec(
            select(MarketplaceListingDraft)
            .where(MarketplaceListingDraft.organization_id == organization_id)
            .order_by(MarketplaceListingDraft.id.asc())
        ).all()
    ]
    live_sale_session = session.exec(
        select(LiveSaleSession)
        .where(LiveSaleSession.organization_id == organization_id)
        .order_by(LiveSaleSession.id.asc())
    ).first()
    assert live_sale_session is not None

    return {
        "owner_email": owner_email,
        "owner_token": owner_token,
        "organization_id": organization_id,
        "ebay_account_id": ebay_account_id,
        "shopify_account_id": shopify_account_id,
        "inventory_item_ids": inventory_item_ids,
        "listing_ids": listing_ids,
        "live_sale_session_id": int(live_sale_session.id or 0),
    }


def _assert_item_order(items: list[dict[str, object]], key: str, expected: list[object]) -> None:
    assert [row[key] for row in items] == expected


def test_p43_regression_cross_subsystem_ordering_replay_and_snapshots(
    client: TestClient,
    session: Session,
) -> None:
    seeded = _seed_regression_org(client, session)
    organization_id = int(seeded["organization_id"])
    owner_token = str(seeded["owner_token"])
    ebay_account_id = int(seeded["ebay_account_id"])
    shopify_account_id = int(seeded["shopify_account_id"])
    inventory_item_ids = [int(value) for value in seeded["inventory_item_ids"]]
    listing_ids = [int(value) for value in seeded["listing_ids"]]
    live_sale_session_id = int(seeded["live_sale_session_id"])

    accounts = client.get(
        f"/api/v1/organizations/{organization_id}/marketplaces?limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert accounts.status_code == 200, accounts.text
    account_items = accounts.json()["data"]["items"]
    _assert_item_order(account_items, "marketplace_type", ["ebay", "shopify"])
    assert account_items[0]["account_status"] == "connected"
    assert account_items[1]["verification_status"] == "pending"

    listings = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-listings?limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert listings.status_code == 200, listings.text
    _assert_item_order(
        listings.json()["data"]["items"],
        "listing_title",
        ["Analytics Listing Ready", "Analytics Listing Invalid"],
    )

    order_first = order_tests._import_order(
        client,
        owner_token,
        organization_id,
        account_id=ebay_account_id,
        order_identifier="p43-regression-order",
        inventory_item_id=inventory_item_ids[0],
        ordered_at="2026-05-29T12:00:00Z",
        total="31.00",
        transaction_reference="p43-regression-txn",
    )
    order_second = order_tests._import_order(
        client,
        owner_token,
        organization_id,
        account_id=ebay_account_id,
        order_identifier="p43-regression-order",
        inventory_item_id=inventory_item_ids[0],
        ordered_at="2026-05-29T12:00:00Z",
        total="31.00",
        transaction_reference="p43-regression-txn",
    )
    assert order_first["order"]["id"] == order_second["order"]["id"]
    assert order_second["import_summary"]["duplicate_detected"] is True

    order_rows = session.exec(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.organization_id == organization_id)
        .order_by(MarketplaceOrder.ordered_at.asc(), MarketplaceOrder.id.asc())
    ).all()
    assert order_rows[0].marketplace_order_identifier == "p43-regression-order"

    sync_run_1 = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/run",
        headers=auth_headers(owner_token),
        json={"marketplace_account_id": shopify_account_id, "sync_run_type": "manual_sync"},
    )
    sync_run_2 = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/run",
        headers=auth_headers(owner_token),
        json={"marketplace_account_id": shopify_account_id, "sync_run_type": "manual_sync"},
    )
    assert sync_run_1.status_code == 201, sync_run_1.text
    assert sync_run_2.status_code == 201, sync_run_2.text

    sync_states = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-sync/states?limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert sync_states.status_code == 200, sync_states.text
    assert sync_states.json()["data"]["items"]

    first_event = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner_token),
        json={
            "marketplace_account_id": ebay_account_id,
            "external_event_identifier": "p43-regression-event-1",
            "event_type": "order_created",
            "event_payload_json": {"order_id": "regression-1"},
            "received_at": "2026-05-29T12:05:00Z",
        },
    )
    second_event = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner_token),
        json={
            "marketplace_account_id": ebay_account_id,
            "external_event_identifier": "p43-regression-event-2",
            "event_type": "order_updated",
            "event_payload_json": {"order_id": "regression-2"},
            "received_at": "2026-05-29T12:06:00Z",
        },
    )
    duplicate_event = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-events/ingest",
        headers=auth_headers(owner_token),
        json={
            "marketplace_account_id": ebay_account_id,
            "external_event_identifier": "p43-regression-event-2",
            "event_type": "order_updated",
            "event_payload_json": {"order_id": "regression-2"},
            "received_at": "2026-05-29T12:06:00Z",
        },
    )
    assert first_event.status_code == 201, first_event.text
    assert second_event.status_code == 201, second_event.text
    assert duplicate_event.status_code == 201, duplicate_event.text
    assert duplicate_event.json()["data"]["event"]["id"] == second_event.json()["data"]["event"]["id"]

    event_rows = session.exec(
        select(MarketplaceEvent)
        .where(MarketplaceEvent.organization_id == organization_id)
        .order_by(MarketplaceEvent.received_at.asc(), MarketplaceEvent.id.asc())
    ).all()
    assert [row.external_event_identifier for row in event_rows[:2]] == [
        "p43-regression-event-1",
        "p43-regression-event-2",
    ]

    offer_first = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers/ingest",
        headers=auth_headers(owner_token),
        json={
            "marketplace_account_id": shopify_account_id,
            "marketplace_listing_draft_id": listing_ids[0],
            "marketplace_offer_identifier": "p43-regression-offer",
            "offer_status": "received",
            "offer_amount": "13.00",
            "offer_currency": "USD",
            "buyer_identifier": "p43-buyer",
        },
    )
    offer_second = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers/ingest",
        headers=auth_headers(owner_token),
        json={
            "marketplace_account_id": shopify_account_id,
            "marketplace_listing_draft_id": listing_ids[0],
            "marketplace_offer_identifier": "p43-regression-offer",
            "offer_status": "received",
            "offer_amount": "13.00",
            "offer_currency": "USD",
            "buyer_identifier": "p43-buyer",
        },
    )
    assert offer_first.status_code == 201, offer_first.text
    assert offer_second.status_code == 201, offer_second.text
    assert offer_first.json()["data"]["id"] == offer_second.json()["data"]["id"]

    offers = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers?limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert offers.status_code == 200, offers.text
    assert offers.json()["data"]["items"][0]["marketplace_offer_identifier"] == "p43-regression-offer"

    add_queue_item = client.post(
        f"/api/v1/organizations/{organization_id}/live-sales/{live_sale_session_id}/queue",
        headers=auth_headers(owner_token),
        json={
            "inventory_item_id": inventory_item_ids[1],
            "marketplace_listing_draft_id": listing_ids[1],
            "planned_price": "17.00",
        },
    )
    assert add_queue_item.status_code == 201, add_queue_item.text

    queue_listing = client.get(
        f"/api/v1/organizations/{organization_id}/live-sales/{live_sale_session_id}/queue?limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert queue_listing.status_code == 200, queue_listing.text
    assert [row["queue_position"] for row in queue_listing.json()["data"]["items"]] == [1, 2]

    mappings = client.get(
        f"/api/v1/organizations/{organization_id}/shopify/mappings?limit=20&offset=0",
        headers=auth_headers(owner_token),
    )
    assert mappings.status_code == 200, mappings.text
    _assert_item_order(
        mappings.json()["data"]["items"],
        "storefront_product_identifier",
        ["analytics-product-2", "analytics-product-1"],
    )

    ops_dashboard = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-ops",
        headers=auth_headers(owner_token),
    )
    assert ops_dashboard.status_code == 200, ops_dashboard.text
    ops_body = ops_dashboard.json()["data"]
    assert ops_body["summary"]["accounts"]["connected"] >= 2
    assert ops_body["summary"]["listings"]["ready"] >= 1
    assert ops_body["summary"]["live_sales"]["active_sessions"] >= 1

    ops_snapshot_1 = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/snapshot",
        headers=auth_headers(owner_token),
    )
    ops_snapshot_2 = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/snapshot",
        headers=auth_headers(owner_token),
    )
    assert ops_snapshot_1.status_code == 201, ops_snapshot_1.text
    assert ops_snapshot_2.status_code == 201, ops_snapshot_2.text
    assert ops_snapshot_2.json()["data"]["id"] > ops_snapshot_1.json()["data"]["id"]

    ops_metrics = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/metrics?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert ops_metrics.status_code == 200, ops_metrics.text
    assert [row["metric_key"] for row in ops_metrics.json()["data"]["items"]] == [
        definition.metric_key for definition in list_marketplace_ops_metric_definitions()
    ]

    ops_diagnostics = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/diagnostics?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert ops_diagnostics.status_code == 200, ops_diagnostics.text
    assert [row["diagnostic_code"] for row in ops_diagnostics.json()["data"]["items"]] == [
        "listing_validation_failures_present",
        "unresolved_sync_conflicts_present",
        "failed_sync_runs_present",
        "transaction_mismatches_present",
        "pending_offer_reviews_present",
        "failed_event_processing_runs_present",
    ]
    ops_snapshots = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-ops/snapshots?limit=10&offset=0",
        headers=auth_headers(owner_token),
    )
    assert ops_snapshots.status_code == 200, ops_snapshots.text
    assert ops_snapshots.json()["data"]["items"][0]["snapshot_type"] == "full_dashboard_snapshot"

    analytics_dashboard = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-analytics",
        headers=auth_headers(owner_token),
    )
    assert analytics_dashboard.status_code == 200, analytics_dashboard.text
    analytics_body = analytics_dashboard.json()["data"]
    assert analytics_body["summary"]["accounts"]["connected_accounts"] >= 1
    assert analytics_body["summary"]["orders"]["imported_orders"] >= 1
    assert analytics_body["summary"]["shopify"]["mapped_products"] >= 1

    analytics_snapshot_1 = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-analytics/generate",
        headers=auth_headers(owner_token),
    )
    analytics_snapshot_2 = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-analytics/generate",
        headers=auth_headers(owner_token),
    )
    assert analytics_snapshot_1.status_code == 201, analytics_snapshot_1.text
    assert analytics_snapshot_2.status_code == 201, analytics_snapshot_2.text
    assert analytics_snapshot_2.json()["data"]["id"] > analytics_snapshot_1.json()["data"]["id"]

    analytics_metrics = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-analytics/metrics?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert analytics_metrics.status_code == 200, analytics_metrics.text
    assert [row["metric_key"] for row in analytics_metrics.json()["data"]["items"]] == [
        definition.metric_key for definition in list_marketplace_kpi_definitions()
    ]

    analytics_trends = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-analytics/trends?limit=50&offset=0",
        headers=auth_headers(owner_token),
    )
    assert analytics_trends.status_code == 200, analytics_trends.text
    assert [row["trend_key"] for row in analytics_trends.json()["data"]["items"]] == [
        definition.trend_key for definition in list_marketplace_trend_definitions()
    ]
    analytics_snapshots = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-analytics/snapshots?limit=10&offset=0",
        headers=auth_headers(owner_token),
    )
    assert analytics_snapshots.status_code == 200, analytics_snapshots.text
    assert analytics_snapshots.json()["data"]["items"][0]["snapshot_type"] == "marketplace_analytics_snapshot"


def test_p43_regression_org_isolation_denies_cross_tenant_access(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "p43-regression-isolation-owner@example.com")
    outsider_token = register_and_login(client, "p43-regression-isolation-outsider@example.com")
    owner_org = analytics_tests._create_organization(client, owner_token, slug="p43-regression-isolation-owner")
    outsider_org = analytics_tests._create_organization(client, outsider_token, slug="p43-regression-isolation-outsider")
    ebay_account = account_tests._connect_marketplace(
        client,
        owner_token,
        owner_org,
        marketplace_type="ebay",
        marketplace_account_id="ebay-p43-regression-isolation",
        display_name="P43 Regression Isolation eBay",
        credential_reference="vault://marketplace/ebay-p43-regression-isolation",
    )
    assert ebay_account.status_code == 201, ebay_account.text
    shopify_account_id = analytics_tests._connect_marketplace_account(client, owner_token, owner_org)
    analytics_tests._seed_analytics_data(
        client,
        session,
        "p43-regression-isolation-owner@example.com",
        owner_token,
        owner_org,
        shopify_account_id,
    )

    denied_routes = [
        f"/api/v1/organizations/{owner_org}/marketplaces",
        f"/api/v1/organizations/{owner_org}/marketplace-listings",
        f"/api/v1/organizations/{owner_org}/marketplace-sync",
        f"/api/v1/organizations/{owner_org}/marketplace-orders",
        f"/api/v1/organizations/{owner_org}/marketplace-pricing",
        f"/api/v1/organizations/{owner_org}/marketplace-events",
        f"/api/v1/organizations/{owner_org}/live-sales",
        f"/api/v1/organizations/{owner_org}/shopify",
        f"/api/v1/organizations/{owner_org}/marketplace-ops",
        f"/api/v1/organizations/{owner_org}/marketplace-analytics",
    ]
    for route in denied_routes:
        response = client.get(route, headers=auth_headers(outsider_token))
        assert response.status_code in {403, 404}, (route, response.status_code, response.text)

    cross_org_routes = [
        f"/api/v1/organizations/{outsider_org}/marketplaces",
        f"/api/v1/organizations/{outsider_org}/marketplace-listings",
        f"/api/v1/organizations/{outsider_org}/marketplace-sync",
        f"/api/v1/organizations/{outsider_org}/marketplace-orders",
        f"/api/v1/organizations/{outsider_org}/marketplace-pricing",
        f"/api/v1/organizations/{outsider_org}/marketplace-events",
        f"/api/v1/organizations/{outsider_org}/live-sales",
        f"/api/v1/organizations/{outsider_org}/shopify",
        f"/api/v1/organizations/{outsider_org}/marketplace-ops",
        f"/api/v1/organizations/{outsider_org}/marketplace-analytics",
    ]
    for route in cross_org_routes:
        response = client.get(route, headers=auth_headers(owner_token))
        assert response.status_code in {403, 404}, (route, response.status_code, response.text)


def test_p43_regression_no_external_clients_in_p43_services() -> None:
    service_files = [
        path
        for path in P43_SERVICE_DIR.iterdir()
        if path.suffix == ".py" and path.name.startswith(("marketplace_", "live_sale_", "shopify_"))
    ]
    assert service_files

    for service_file in service_files:
        source = service_file.read_text(encoding="utf-8")
        for marker in P43_EXTERNAL_CLIENT_MARKERS:
            assert marker not in source, f"{marker} found in {service_file.name}"
