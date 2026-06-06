from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.market_pricing_engine import P68InventoryComputedFmv, P68MarketPriceSnapshot
from app.services.exit_queue_service import build_exit_queue_snapshot, list_exit_queue_items
from app.services.exit_recommendation_service import build_exit_recommendation_snapshot
from app.services.investor_sell_dashboard_service import build_investor_sell_dashboard_snapshot
from app.services.liquidity_intelligence_service import build_liquidity_snapshot
from app.services.listing_intelligence_service import build_listing_recommendation_snapshot
from app.services.p71_sell_context import load_sell_intel_contexts
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_market_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    copy: InventoryCopy,
    title: str,
    publisher: str,
    issue_number: str,
    computed_fmv: float,
    weighted_median: float,
    liquidity_score: float,
    sales_velocity: float,
    confidence: float,
    trend: str,
    provider_breakdown: dict[str, int],
) -> None:
    snapshot = P68MarketPriceSnapshot(
        owner_user_id=owner_user_id,
        generated_at=datetime.now(timezone.utc),
        inventory_copy_id=int(copy.id or 0),
        title=title,
        publisher=publisher,
        issue_number=issue_number,
        raw_fmv=round(computed_fmv * 0.95, 2),
        graded_fmv=round(computed_fmv * 1.1, 2),
        blended_fmv=computed_fmv,
        low_sale=round(weighted_median * 0.88, 2),
        high_sale=round(weighted_median * 1.14, 2),
        median_sale=weighted_median,
        average_sale=round((weighted_median + computed_fmv) / 2.0, 2),
        sales_count=max(1, int(round(sales_velocity * 3))),
        liquidity_score=liquidity_score,
        confidence=confidence,
        price_trend_30d=trend,
        price_trend_90d=trend,
        primary_provider="EBAY_SOLD",
        metadata_json={
            "weighted_median_sale": weighted_median,
            "recent_median_30d": round(weighted_median * 1.02, 2),
            "recent_median_90d": round(weighted_median * 0.98, 2),
            "sales_velocity": sales_velocity,
            "liquidity_band": "VERY_HIGH" if liquidity_score >= 75 else "HIGH" if liquidity_score >= 55 else "MEDIUM",
            "provider_breakdown": provider_breakdown,
            "primary_provider": "EBAY_SOLD",
        },
    )
    session.add(snapshot)
    session.flush()
    session.add(
        P68InventoryComputedFmv(
            owner_user_id=owner_user_id,
            inventory_copy_id=int(copy.id or 0),
            snapshot_id=int(snapshot.id or 0),
            computed_fmv=computed_fmv,
            computed_fmv_source="P70-04_EBAY",
            confidence=confidence,
            provider_blend_json={"EBAY_SOLD": computed_fmv},
        )
    )
    session.commit()


def test_p71_pipeline_uses_ebay_market_inputs_for_queue_and_dashboard(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p70-integration@example.com")
    owner_id = _owner_id(session, "p70-integration@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Amazing Spider-Man",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 20.00,
            },
            {
                "title": "Moon Knight",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 18.00,
            },
        ],
    )
    copies = list(
        session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id).order_by(InventoryCopy.id.asc())).all()
    )
    assert len(copies) >= 2

    _seed_market_snapshot(
        session,
        owner_user_id=owner_id,
        copy=copies[0],
        title="Amazing Spider-Man",
        publisher="Marvel",
        issue_number="1",
        computed_fmv=96.0,
        weighted_median=94.0,
        liquidity_score=88.0,
        sales_velocity=4.5,
        confidence=0.84,
        trend="RISING",
        provider_breakdown={"EBAY_SOLD": 8, "INTERNAL_SALE": 1},
    )
    _seed_market_snapshot(
        session,
        owner_user_id=owner_id,
        copy=copies[1],
        title="Moon Knight",
        publisher="Marvel",
        issue_number="1",
        computed_fmv=41.0,
        weighted_median=39.0,
        liquidity_score=24.0,
        sales_velocity=0.4,
        confidence=0.42,
        trend="STABLE",
        provider_breakdown={"EBAY_SOLD": 2},
    )

    exit_snap = build_exit_recommendation_snapshot(session, owner_user_id=owner_id)
    listing_snap = build_listing_recommendation_snapshot(session, owner_user_id=owner_id)
    liquidity_snap = build_liquidity_snapshot(session, owner_user_id=owner_id)
    queue_snap = build_exit_queue_snapshot(session, owner_user_id=owner_id)
    dashboard_snap = build_investor_sell_dashboard_snapshot(session, owner_user_id=owner_id)

    contexts = load_sell_intel_contexts(session, owner_user_id=owner_id)
    assert len(contexts) == 2
    assert contexts[0].market_timing_signal in {"SELL_NOW", "SELL_SOON"}
    assert any(ctx.market_timing_signal == "HOLD" for ctx in contexts)

    queue_items = list_exit_queue_items(session, snapshot_id=int(queue_snap.id or 0))
    assert queue_items[0].inventory_copy_id == copies[0].id
    assert queue_items[0].factors_json["market_strength"] >= queue_items[-1].factors_json["market_strength"]

    assert exit_snap.metadata_json["avg_market_liquidity"] > 0
    assert listing_snap.metadata_json["avg_market_sales_velocity"] > 0
    assert liquidity_snap.metadata_json["avg_market_confidence"] > 0
    assert dashboard_snap.metadata_json["sell_now_count"] >= 1
    assert any(card["title"] == contexts[0].title for card in dashboard_snap.cards_json["sell_now"])
    assert dashboard_snap.cards_json["timing_signals"]["SELL_NOW"] >= 1
    assert dashboard_snap.cards_json["market_overview"]["avg_sales_velocity"] > 0
