from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    InventoryCopy,
    LiveSaleClaim,
    LiveSaleQueueItem,
    LiveSaleSession,
    MarketplaceAccount,
    MarketplaceAnalyticsEvent,
    MarketplaceAnalyticsSnapshot,
    MarketplaceEvent,
    MarketplaceEventProcessingRun,
    MarketplaceInventoryConflict,
    MarketplaceInventoryState,
    MarketplaceInventorySyncRun,
    MarketplaceListingDraft,
    MarketplaceMetric,
    MarketplaceOffer,
    MarketplaceOrder,
    MarketplacePerformanceTrend,
    MarketplacePriceRecommendation,
    MarketplaceTransaction,
    ShopifyProductMapping,
    ShopifyStorefront,
    ShopifySyncState,
    User,
)
from app.services.live_sale_claim_service import CLAIM_STATUS_CLAIMED
from app.services.live_sale_queue_service import QUEUE_ITEM_STATUS_SOLD
from app.services.live_sale_workflow_service import SESSION_STATUS_LIVE
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED
from app.services.marketplace_event_processing import EVENT_STATUS_PROCESSED, PROCESSING_STATUS_FAILED
from app.services.marketplace_inventory_sync_service import CONFLICT_STATUS_DETECTED, SYNC_STATUS_FAILED
from app.services.marketplace_kpi_registry import list_marketplace_kpi_definitions
from app.services.marketplace_listing_validation import LISTING_STATUS_READY, VALIDATION_STATUS_INVALID, VALIDATION_STATUS_VALID
from app.services.marketplace_offer_service import OFFER_STATUS_RECEIVED
from app.services.marketplace_order_ingestion import (
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_IMPORTED,
    ORDER_STATUS_PENDING,
    TRANSACTION_STATUS_COMPLETED,
    TRANSACTION_STATUS_FAILED,
)
from app.services.marketplace_pricing_service import RECOMMENDATION_STATUS_GENERATED, RECOMMENDATION_STATUS_REVIEWED
from app.services.marketplace_trends import list_marketplace_trend_definitions
from app.services.shopify_publication_registry import MAPPING_STATUS_INVALID, MAPPING_STATUS_MAPPED
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
            "marketplace_account_id": "analytics-shopify-account",
            "display_name": "Analytics Shopify",
            "credential_type": "oauth_token",
            "credential_reference": "vault://marketplace/analytics-shopify-account",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _seed_inventory_items(client: TestClient, token: str) -> None:
    for index in range(2):
        create_order(
            client,
            token,
            items=[
                {
                    "title": f"Analytics Inventory {index + 1}",
                    "publisher": "Image",
                    "issue_number": str(index + 1),
                    "cover_name": f"Cover {index + 1}",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 6.00 + index,
                }
            ],
        )


def _seed_analytics_data(
    client: TestClient,
    session: Session,
    owner_email: str,
    token: str,
    organization_id: int,
    account_id: int,
) -> None:
    _seed_inventory_items(client, token)
    user = session.exec(select(User).where(User.email == owner_email)).one()
    inventory_items = session.exec(
        select(InventoryCopy).where(InventoryCopy.user_id == user.id).order_by(InventoryCopy.id.asc()).limit(2)
    ).all()
    assert len(inventory_items) == 2

    listing_ready = MarketplaceListingDraft(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        inventory_item_id=int(inventory_items[0].id or 0),
        listing_title="Analytics Listing Ready",
        listing_description="Ready listing for analytics",
        listing_price=Decimal("12.00"),
        listing_currency="USD",
        listing_quantity=1,
        listing_status=LISTING_STATUS_READY,
        validation_status=VALIDATION_STATUS_VALID,
        created_by_user_id=int(user.id or 0),
    )
    listing_invalid = MarketplaceListingDraft(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        inventory_item_id=int(inventory_items[1].id or 0),
        listing_title="Analytics Listing Invalid",
        listing_description="Invalid listing for analytics",
        listing_price=Decimal("14.00"),
        listing_currency="USD",
        listing_quantity=1,
        listing_status=LISTING_STATUS_READY,
        validation_status=VALIDATION_STATUS_INVALID,
        created_by_user_id=int(user.id or 0),
    )
    session.add_all([listing_ready, listing_invalid])
    session.flush()

    inventory_state = MarketplaceInventoryState(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_listing_draft_id=int(listing_invalid.id or 0),
        marketplace_listing_identifier="analytics-listing-invalid",
        inventory_item_id=int(inventory_items[1].id or 0),
        local_quantity=1,
        marketplace_quantity=0,
        sync_status=SYNC_STATUS_FAILED,
    )
    session.add(inventory_state)
    session.flush()
    session.add(
        MarketplaceInventoryConflict(
            organization_id=organization_id,
            marketplace_inventory_state_id=int(inventory_state.id or 0),
            conflict_type="quantity_mismatch",
            local_value_json={"local_quantity": 1},
            marketplace_value_json={"marketplace_quantity": 0},
            conflict_status=CONFLICT_STATUS_DETECTED,
        )
    )
    session.add(
        MarketplaceInventorySyncRun(
            organization_id=organization_id,
            marketplace_account_id=account_id,
            sync_run_type="inventory_sync",
            sync_status=SYNC_STATUS_FAILED,
            records_processed=2,
            conflicts_detected=1,
        )
    )

    order_imported = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="analytics-order-imported",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_IMPORTED,
        buyer_identifier="buyer-1",
        order_total=Decimal("15.00"),
        order_currency="USD",
    )
    order_pending = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="analytics-order-pending",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_PENDING,
        buyer_identifier="buyer-2",
        order_total=Decimal("18.00"),
        order_currency="USD",
    )
    order_completed = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="analytics-order-completed",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_COMPLETED,
        buyer_identifier="buyer-3",
        order_total=Decimal("21.00"),
        order_currency="USD",
    )
    order_cancelled = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_order_identifier="analytics-order-cancelled",
        marketplace_type="shopify",
        order_status=ORDER_STATUS_CANCELLED,
        buyer_identifier="buyer-4",
        order_total=Decimal("24.00"),
        order_currency="USD",
    )
    session.add_all([order_imported, order_pending, order_completed, order_cancelled])
    session.flush()
    session.add(
        MarketplaceTransaction(
            organization_id=organization_id,
            marketplace_order_id=int(order_imported.id or 0),
            transaction_type="sale",
            transaction_status=TRANSACTION_STATUS_COMPLETED,
            gross_amount=Decimal("15.00"),
            fee_amount=Decimal("1.50"),
            net_amount=Decimal("13.50"),
            transaction_currency="USD",
            transaction_reference="analytics-tx-completed",
        )
    )
    session.add(
        MarketplaceTransaction(
            organization_id=organization_id,
            marketplace_order_id=int(order_pending.id or 0),
            transaction_type="sale",
            transaction_status=TRANSACTION_STATUS_FAILED,
            gross_amount=Decimal("18.00"),
            fee_amount=Decimal("1.80"),
            net_amount=Decimal("16.20"),
            transaction_currency="USD",
            transaction_reference="analytics-tx-failed",
        )
    )

    session.add(
        MarketplacePriceRecommendation(
            organization_id=organization_id,
            marketplace_account_id=account_id,
            marketplace_listing_draft_id=int(listing_ready.id or 0),
            inventory_item_id=int(inventory_items[0].id or 0),
            recommendation_type="markdown",
            recommended_price=Decimal("10.00"),
            current_listing_price=Decimal("12.00"),
            floor_price=Decimal("9.00"),
            ceiling_price=Decimal("13.00"),
            recommendation_reason="Analytics seed recommendation",
            recommendation_status=RECOMMENDATION_STATUS_GENERATED,
        )
    )
    session.add(
        MarketplacePriceRecommendation(
            organization_id=organization_id,
            marketplace_account_id=account_id,
            marketplace_listing_draft_id=int(listing_ready.id or 0),
            inventory_item_id=int(inventory_items[0].id or 0),
            recommendation_type="markdown",
            recommended_price=Decimal("9.00"),
            current_listing_price=Decimal("12.00"),
            floor_price=Decimal("8.00"),
            ceiling_price=Decimal("13.00"),
            recommendation_reason="Analytics reviewed recommendation",
            recommendation_status=RECOMMENDATION_STATUS_REVIEWED,
        )
    )
    session.add(
        MarketplaceOffer(
            organization_id=organization_id,
            marketplace_account_id=account_id,
            marketplace_listing_draft_id=int(listing_ready.id or 0),
            marketplace_offer_identifier="analytics-offer-1",
            offer_status=OFFER_STATUS_RECEIVED,
            offer_amount=Decimal("11.00"),
            offer_currency="USD",
            buyer_identifier="offer-buyer-1",
        )
    )

    marketplace_event = MarketplaceEvent(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        marketplace_type="shopify",
        external_event_identifier="analytics-event-1",
        event_type="order_update",
        event_status=EVENT_STATUS_PROCESSED,
        event_payload_json={"event": "processed"},
    )
    session.add(marketplace_event)
    session.flush()
    session.add(
        MarketplaceEventProcessingRun(
            organization_id=organization_id,
            marketplace_event_id=int(marketplace_event.id or 0),
            processing_status=PROCESSING_STATUS_FAILED,
            processing_result_json={"reason": "analytics seed failure"},
        )
    )

    live_session = LiveSaleSession(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        session_name="Analytics Live Sale",
        session_status=SESSION_STATUS_LIVE,
        created_by_user_id=int(user.id or 0),
    )
    session.add(live_session)
    session.flush()
    queue_item = LiveSaleQueueItem(
        organization_id=organization_id,
        live_sale_session_id=int(live_session.id or 0),
        inventory_item_id=int(inventory_items[0].id or 0),
        marketplace_listing_draft_id=int(listing_ready.id or 0),
        queue_position=1,
        item_status=QUEUE_ITEM_STATUS_SOLD,
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

    storefront = ShopifyStorefront(
        organization_id=organization_id,
        marketplace_account_id=account_id,
        storefront_name="Analytics Storefront",
        storefront_status="published_internal",
        storefront_identifier="analytics-storefront",
    )
    session.add(storefront)
    session.flush()
    session.add(
        ShopifyProductMapping(
            organization_id=organization_id,
            inventory_item_id=int(inventory_items[0].id or 0),
            marketplace_listing_draft_id=int(listing_ready.id or 0),
            storefront_product_identifier="analytics-product-1",
            mapping_status=MAPPING_STATUS_MAPPED,
        )
    )
    session.add(
        ShopifyProductMapping(
            organization_id=organization_id,
            inventory_item_id=int(inventory_items[1].id or 0),
            marketplace_listing_draft_id=int(listing_invalid.id or 0),
            storefront_product_identifier="analytics-product-2",
            mapping_status=MAPPING_STATUS_INVALID,
        )
    )
    session.add(
        ShopifySyncState(
            organization_id=organization_id,
            storefront_id=int(storefront.id or 0),
            sync_status="completed",
            sync_payload_json={"status": "completed"},
        )
    )
    session.commit()


def test_marketplace_analytics_generation_kpis_trends_and_snapshot(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "marketplace-analytics-owner@example.com")
    organization_id = _create_organization(client, owner_token, slug="marketplace-analytics-org")
    account_id = _connect_marketplace_account(client, owner_token, organization_id)
    _seed_analytics_data(client, session, "marketplace-analytics-owner@example.com", owner_token, organization_id, account_id)

    dashboard = client.get(f"/api/v1/organizations/{organization_id}/marketplace-analytics", headers=auth_headers(owner_token))
    assert dashboard.status_code == 200, dashboard.text
    dashboard_body = dashboard.json()["data"]
    assert dashboard_body["summary"]["accounts"]["connected_accounts"] == 1
    assert dashboard_body["summary"]["listings"]["listing_validation_rate"] == 0.5
    assert dashboard_body["summary"]["orders"]["imported_orders"] == 1
    assert dashboard_body["summary"]["orders"]["total_sales_amount"] == "15.00"
    assert dashboard_body["summary"]["orders"]["average_order_value"] == "15.00"
    assert dashboard_body["summary"]["transactions"]["reconciliation_success_rate"] == 0.5
    assert dashboard_body["summary"]["pricing"]["recommendations_generated"] == 1
    assert dashboard_body["summary"]["pricing"]["reviewed_recommendations"] == 1
    assert dashboard_body["summary"]["pricing"]["received_offers"] == 1
    assert dashboard_body["summary"]["events"]["processed_events"] == 1
    assert dashboard_body["summary"]["events"]["duplicate_event_rate"] == 0.0
    assert dashboard_body["summary"]["live_sales"]["total_live_sale_sessions"] == 1
    assert dashboard_body["summary"]["live_sales"]["sold_live_sale_items"] == 1
    assert dashboard_body["summary"]["live_sales"]["claim_conversion_rate"] == 1.0
    assert dashboard_body["summary"]["shopify"]["mapped_products"] == 1
    assert dashboard_body["summary"]["shopify"]["valid_product_mappings"] == 1
    assert dashboard_body["summary"]["sync"]["latest_sync_status"] == "failed"
    assert dashboard_body["summary"]["sync"]["open_conflicts"] == 1
    assert dashboard_body["summary"]["shopify"]["storefronts"] == 1

    snapshot = client.post(f"/api/v1/organizations/{organization_id}/marketplace-analytics/generate", headers=auth_headers(owner_token))
    assert snapshot.status_code == 201, snapshot.text
    snapshot_body = snapshot.json()["data"]
    assert snapshot_body["snapshot_type"] == "marketplace_analytics_snapshot"
    assert snapshot_body["snapshot_payload_json"]["summary"]["orders"]["imported_orders"] == 1
    assert snapshot_body["snapshot_payload_json"]["summary"]["live_sales"]["claim_conversion_rate"] == 1.0
    assert len(snapshot_body["snapshot_payload_json"]["metrics"]) == len(list_marketplace_kpi_definitions())
    assert len(snapshot_body["snapshot_payload_json"]["trends"]) == len(list_marketplace_trend_definitions())

    metrics = client.get(f"/api/v1/organizations/{organization_id}/marketplace-analytics/metrics?limit=50&offset=0", headers=auth_headers(owner_token))
    assert metrics.status_code == 200, metrics.text
    assert [row["metric_key"] for row in metrics.json()["data"]["items"]] == [
        definition.metric_key for definition in list_marketplace_kpi_definitions()
    ]

    trends = client.get(f"/api/v1/organizations/{organization_id}/marketplace-analytics/trends?limit=50&offset=0", headers=auth_headers(owner_token))
    assert trends.status_code == 200, trends.text
    assert [row["trend_key"] for row in trends.json()["data"]["items"]] == [
        definition.trend_key for definition in list_marketplace_trend_definitions()
    ]

    snapshots = client.get(f"/api/v1/organizations/{organization_id}/marketplace-analytics/snapshots?limit=10&offset=0", headers=auth_headers(owner_token))
    assert snapshots.status_code == 200, snapshots.text
    assert snapshots.json()["data"]["items"][0]["snapshot_type"] == "marketplace_analytics_snapshot"

    session.expire_all()
    events = session.exec(
        select(MarketplaceAnalyticsEvent)
        .where(MarketplaceAnalyticsEvent.organization_id == organization_id)
        .order_by(MarketplaceAnalyticsEvent.created_at.asc(), MarketplaceAnalyticsEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "marketplace_analytics_generated",
        "marketplace_metrics_generated",
        "marketplace_trends_generated",
        "marketplace_performance_calculated",
        "marketplace_snapshot_generated",
    ]

    stored_metrics = session.exec(select(MarketplaceMetric).where(MarketplaceMetric.organization_id == organization_id)).all()
    stored_trends = session.exec(select(MarketplacePerformanceTrend).where(MarketplacePerformanceTrend.organization_id == organization_id)).all()
    stored_snapshots = session.exec(select(MarketplaceAnalyticsSnapshot).where(MarketplaceAnalyticsSnapshot.organization_id == organization_id)).all()
    assert len(stored_metrics) == len(list_marketplace_kpi_definitions())
    assert len(stored_trends) == len(list_marketplace_trend_definitions())
    assert len(stored_snapshots) == 1


def test_marketplace_analytics_org_isolation_and_unauthorized_lineage(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "marketplace-analytics-isolation-owner@example.com")
    outsider_token = register_and_login(client, "marketplace-analytics-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner_token, slug="marketplace-analytics-isolation-org")
    _connect_marketplace_account(client, owner_token, organization_id)

    denied = client.get(f"/api/v1/organizations/{organization_id}/marketplace-analytics", headers=auth_headers(outsider_token))
    assert denied.status_code == 403, denied.text

    session.expire_all()
    unauthorized_events = session.exec(
        select(MarketplaceAnalyticsEvent)
        .where(MarketplaceAnalyticsEvent.organization_id == organization_id)
        .where(MarketplaceAnalyticsEvent.event_type == "unauthorized_marketplace_analytics_access_attempt")
    ).all()
    assert unauthorized_events
