from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    InventoryCopy,
    LiveSaleClaim,
    LiveSaleQueueItem,
    LiveSaleSession,
    MarketplaceAccount,
    MarketplaceEvent,
    MarketplaceEventProcessingRun,
    MarketplaceInventoryConflict,
    MarketplaceInventoryState,
    MarketplaceInventorySyncRun,
    MarketplaceListingDraft,
    MarketplaceOpsDiagnostic,
    MarketplaceOpsEvent,
    MarketplaceOpsMetric,
    MarketplaceOpsSnapshot,
    MarketplaceOffer,
    MarketplaceOrder,
    MarketplacePriceRecommendation,
    MarketplaceTransaction,
    MarketplaceEventLineage,
    User,
)
from app.services.live_sale_claim_service import CLAIM_STATUS_CLAIMED
from app.services.live_sale_queue_service import QUEUE_ITEM_STATUS_QUEUED
from app.services.live_sale_workflow_service import SESSION_STATUS_LIVE
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED
from app.services.marketplace_account_service import VERIFICATION_STATUS_VERIFIED
from app.services.marketplace_event_processing import EVENT_STATUS_RECEIVED, PROCESSING_STATUS_FAILED
from app.services.marketplace_inventory_sync_service import CONFLICT_STATUS_DETECTED
from app.services.marketplace_listing_validation import LISTING_STATUS_READY, VALIDATION_STATUS_INVALID
from app.services.marketplace_offer_service import OFFER_STATUS_RECEIVED
from app.services.marketplace_order_ingestion import (
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_IMPORTED,
    ORDER_STATUS_PENDING,
    TRANSACTION_STATUS_FAILED,
)
from app.services.marketplace_pricing_service import RECOMMENDATION_STATUS_GENERATED
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _connect_marketplace_account(client: TestClient, token: str, organization_id: int) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": "shopify",
            "marketplace_account_id": "shopify-ops-account",
            "display_name": "Shopify Ops",
            "credential_type": "oauth_token",
            "credential_reference": "vault://marketplace/shopify-ops-account",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _seed_ops_data(client: TestClient, session: Session, owner_email: str, token: str, organization_id: int, account_id: int) -> dict[str, int]:
    for index in range(2):
        create_order(
            client,
            token,
            items=[
                {
                    "title": f"Ops Inventory {index + 1}",
                    "publisher": "Image",
                    "issue_number": str(index + 1),
                    "cover_name": f"Cover {index + 1}",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 7.00 + index,
                }
            ],
        )

    owner_id = session.exec(select(User).where(User.email == owner_email)).one().id
    inventory_items = session.exec(
        select(InventoryCopy)
        .where(InventoryCopy.user_id == owner_id)
        .order_by(InventoryCopy.id.asc())
        .limit(2)
    ).all()
    assert len(inventory_items) == 2

    listing_ready = MarketplaceListingDraft(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        inventory_item_id=int(inventory_items[0].id or 0),
        listing_title="Ops Listing Ready",
        listing_description="Ready listing for dashboard metrics",
        listing_price=12.00,
        listing_currency="USD",
        listing_quantity=1,
        listing_status=LISTING_STATUS_READY,
        validation_status="valid",
        created_by_user_id=owner_id,
    )
    listing_invalid = MarketplaceListingDraft(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        inventory_item_id=int(inventory_items[1].id or 0),
        listing_title="Ops Listing Invalid",
        listing_description="Invalid listing for diagnostics",
        listing_price=13.00,
        listing_currency="USD",
        listing_quantity=1,
        listing_status=LISTING_STATUS_READY,
        validation_status=VALIDATION_STATUS_INVALID,
        created_by_user_id=owner_id,
    )
    session.add(listing_ready)
    session.add(listing_invalid)
    session.flush()
    inventory_state = MarketplaceInventoryState(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_listing_draft_id=int(listing_invalid.id or 0),
        marketplace_listing_identifier="ops-listing-invalid",
        inventory_item_id=int(inventory_items[1].id or 0),
        local_quantity=1,
        marketplace_quantity=0,
        sync_status="failed",
    )
    session.add(inventory_state)
    session.flush()

    sync_run = MarketplaceInventorySyncRun(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        sync_run_type="inventory_sync",
        sync_status="failed",
        records_processed=4,
        conflicts_detected=1,
    )
    conflict = MarketplaceInventoryConflict(
        organization_id=organization_id,
        marketplace_inventory_state_id=int(inventory_state.id or 0),
        conflict_type="quantity_mismatch",
        local_value_json={"local_quantity": 1},
        marketplace_value_json={"marketplace_quantity": 0},
        conflict_status=CONFLICT_STATUS_DETECTED,
    )
    session.add(sync_run)
    session.add(conflict)

    order_imported = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="ops-order-imported",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_IMPORTED,
        buyer_identifier="buyer-1",
        order_total=15.00,
        order_currency="USD",
    )
    order_pending = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="ops-order-pending",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_PENDING,
        buyer_identifier="buyer-2",
        order_total=18.00,
        order_currency="USD",
    )
    order_completed = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="ops-order-completed",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_COMPLETED,
        buyer_identifier="buyer-3",
        order_total=21.00,
        order_currency="USD",
    )
    order_cancelled = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="ops-order-cancelled",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_CANCELLED,
        buyer_identifier="buyer-4",
        order_total=24.00,
        order_currency="USD",
    )
    session.add_all([order_imported, order_pending, order_completed, order_cancelled])
    session.flush()
    session.add(
        MarketplaceTransaction(
            organization_id=organization_id,
            marketplace_order_id=int(order_imported.id or 0),
            transaction_type="sale",
            transaction_status=TRANSACTION_STATUS_FAILED,
            gross_amount=15.00,
            fee_amount=1.50,
            net_amount=13.50,
            transaction_currency="USD",
            transaction_reference="ops-tx-1",
        )
    )

    session.add(
        MarketplacePriceRecommendation(
            organization_id=organization_id,
            marketplace_account_id=account_id,
            marketplace_listing_draft_id=int(listing_ready.id or 0),
            inventory_item_id=int(inventory_items[0].id or 0),
            recommendation_type="markdown",
            recommended_price=10.00,
            current_listing_price=12.00,
            floor_price=9.00,
            ceiling_price=13.00,
            recommendation_reason="Ops diagnostics seed",
            recommendation_status=RECOMMENDATION_STATUS_GENERATED,
        )
    )
    session.add(
        MarketplaceOffer(
            organization_id=organization_id,
            marketplace_account_id=account_id,
            marketplace_listing_draft_id=int(listing_ready.id or 0),
            marketplace_offer_identifier="ops-offer-1",
            offer_status=OFFER_STATUS_RECEIVED,
            offer_amount=11.00,
            offer_currency="USD",
            buyer_identifier="offer-buyer-1",
        )
    )
    marketplace_event = MarketplaceEvent(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_type="shopify",
        external_event_identifier="ops-event-1",
        event_type="order_update",
        event_status=EVENT_STATUS_RECEIVED,
        event_payload_json={"event": "received"},
    )
    session.add(marketplace_event)
    session.flush()
    session.add(
        MarketplaceEventProcessingRun(
            organization_id=organization_id,
            marketplace_event_id=int(marketplace_event.id or 0),
            processing_status=PROCESSING_STATUS_FAILED,
            processing_result_json={"reason": "seed failure"},
        )
    )

    live_session = LiveSaleSession(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        session_name="Ops Live Sale",
        session_status=SESSION_STATUS_LIVE,
        created_by_user_id=owner_id,
    )
    session.add(live_session)
    session.flush()
    queue_item = LiveSaleQueueItem(
        organization_id=organization_id,
        live_sale_session_id=int(live_session.id or 0),
        inventory_item_id=int(inventory_items[0].id or 0),
        marketplace_listing_draft_id=int(listing_ready.id or 0),
        queue_position=1,
        item_status=QUEUE_ITEM_STATUS_QUEUED,
    )
    session.add(queue_item)
    session.flush()
    session.add(
        LiveSaleClaim(
            organization_id=organization_id,
            live_sale_session_id=int(live_session.id or 0),
            live_sale_queue_item_id=int(queue_item.id or 0),
            buyer_identifier="claim-buyer-1",
            claim_status=CLAIM_STATUS_CLAIMED,
        )
    )
    session.commit()

    return {
        "listing_ready_id": int(listing_ready.id or 0),
        "listing_invalid_id": int(listing_invalid.id or 0),
        "live_session_id": int(live_session.id or 0),
    }


def test_marketplace_ops_dashboard_metrics_diagnostics_snapshot_and_lineage(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "marketplace-ops-owner@example.com")
    organization_id = _create_organization(client, owner_token, slug="marketplace-ops-org")
    account_id = _connect_marketplace_account(client, owner_token, organization_id)
    seeded = _seed_ops_data(client, session, "marketplace-ops-owner@example.com", owner_token, organization_id, account_id)

    dashboard = client.get(f"/api/v1/organizations/{organization_id}/marketplace-ops", headers=auth_headers(owner_token))
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()["data"]
    assert body["summary"]["accounts"]["connected"] == 1
    assert body["summary"]["listings"]["invalid"] == 1
    assert body["summary"]["sync"]["open_conflicts"] == 1
    assert body["summary"]["orders"]["imported"] == 1
    assert body["summary"]["pricing"]["received_offers"] == 1
    assert body["summary"]["events"]["failed_processing_runs"] == 1
    assert body["summary"]["live_sales"]["active_sessions"] == 1

    diagnostics = client.post(f"/api/v1/organizations/{organization_id}/marketplace-ops/diagnostics/generate", headers=auth_headers(owner_token))
    assert diagnostics.status_code == 201, diagnostics.text
    diagnostic_codes = [row["diagnostic_code"] for row in diagnostics.json()["data"]["items"]]
    assert diagnostic_codes == [
        "listing_validation_failures_present",
        "unresolved_sync_conflicts_present",
        "failed_sync_runs_present",
        "transaction_mismatches_present",
        "pending_offer_reviews_present",
        "failed_event_processing_runs_present",
    ]

    snapshot = client.post(f"/api/v1/organizations/{organization_id}/marketplace-ops/snapshot", headers=auth_headers(owner_token))
    assert snapshot.status_code == 201, snapshot.text
    snapshot_body = snapshot.json()["data"]
    assert snapshot_body["snapshot_type"] == "full_dashboard_snapshot"
    assert snapshot_body["snapshot_payload_json"]["summary"]["accounts"]["connected"] == 1
    assert snapshot_body["snapshot_payload_json"]["summary"]["live_sales"]["claims"] == 1

    metrics = client.get(f"/api/v1/organizations/{organization_id}/marketplace-ops/metrics?limit=50&offset=0", headers=auth_headers(owner_token))
    assert metrics.status_code == 200, metrics.text
    metric_keys = [row["metric_key"] for row in metrics.json()["data"]["items"]]
    assert metric_keys == [
        "connected_marketplace_accounts",
        "verified_marketplace_accounts",
        "active_listing_drafts",
        "ready_listing_drafts",
        "invalid_listing_drafts",
        "latest_sync_run_status",
        "open_sync_conflicts",
        "imported_orders_count",
        "pending_orders_count",
        "completed_orders_count",
        "failed_orders_count",
        "transaction_mismatches_count",
        "pending_pricing_recommendations",
        "received_offers_count",
        "unprocessed_events_count",
        "failed_event_processing_runs_count",
        "active_live_sale_sessions",
        "live_sale_claims_count",
    ]

    snapshots = client.get(f"/api/v1/organizations/{organization_id}/marketplace-ops/snapshots?limit=10&offset=0", headers=auth_headers(owner_token))
    assert snapshots.status_code == 200, snapshots.text
    assert snapshots.json()["data"]["items"][0]["snapshot_type"] == "full_dashboard_snapshot"

    session.expire_all()
    events = session.exec(
        select(MarketplaceOpsEvent)
        .where(MarketplaceOpsEvent.organization_id == organization_id)
        .order_by(MarketplaceOpsEvent.created_at.asc(), MarketplaceOpsEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "marketplace_ops_dashboard_accessed",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostics_generated",
        "marketplace_ops_metrics_generated",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostic_created",
        "marketplace_ops_diagnostics_generated",
        "marketplace_ops_snapshot_generated",
    ]

    stored_metrics = session.exec(select(MarketplaceOpsMetric).where(MarketplaceOpsMetric.organization_id == organization_id)).all()
    stored_diagnostics = session.exec(select(MarketplaceOpsDiagnostic).where(MarketplaceOpsDiagnostic.organization_id == organization_id)).all()
    stored_snapshots = session.exec(select(MarketplaceOpsSnapshot).where(MarketplaceOpsSnapshot.organization_id == organization_id)).all()
    assert len(stored_metrics) == 18
    assert len(stored_diagnostics) == 12
    assert len(stored_snapshots) == 1
    assert seeded["live_session_id"] > 0


def test_marketplace_ops_dashboard_org_isolation_and_unauthorized_lineage(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "marketplace-ops-isolation-owner@example.com")
    outsider_token = register_and_login(client, "marketplace-ops-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner_token, slug="marketplace-ops-isolation-org")
    _connect_marketplace_account(client, owner_token, organization_id)

    denied = client.get(f"/api/v1/organizations/{organization_id}/marketplace-ops", headers=auth_headers(outsider_token))
    assert denied.status_code == 403, denied.text

    session.expire_all()
    unauthorized_events = session.exec(
        select(MarketplaceOpsEvent)
        .where(MarketplaceOpsEvent.organization_id == organization_id)
        .where(MarketplaceOpsEvent.event_type == "unauthorized_marketplace_ops_access_attempt")
    ).all()
    assert unauthorized_events
