"""P71-02 Listing intelligence."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.sell_intelligence_platform import P71ListingRecommendationItem, P71ListingRecommendationSnapshot, utc_now
from app.services.p71_sell_context import load_sell_intel_contexts
from app.services.p71_sell_scoring import score_listing


def get_latest_listing_snapshot(session: Session, *, owner_user_id: int) -> P71ListingRecommendationSnapshot | None:
    return session.exec(
        select(P71ListingRecommendationSnapshot)
        .where(P71ListingRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P71ListingRecommendationSnapshot.generated_at.desc(), P71ListingRecommendationSnapshot.id.desc())
    ).first()


def list_listing_items(session: Session, *, snapshot_id: int, limit: int = 200) -> list[P71ListingRecommendationItem]:
    return list(
        session.exec(
            select(P71ListingRecommendationItem)
            .where(P71ListingRecommendationItem.snapshot_id == snapshot_id)
            .order_by(P71ListingRecommendationItem.expected_profit.desc(), P71ListingRecommendationItem.id.asc())
            .limit(min(max(limit, 1), 500))
        ).all()
    )


def build_listing_recommendation_snapshot(session: Session, *, owner_user_id: int) -> P71ListingRecommendationSnapshot:
    today = date.today()
    contexts = load_sell_intel_contexts(session, owner_user_id=owner_user_id)
    snap = P71ListingRecommendationSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
    )
    session.add(snap)
    session.flush()

    count = 0
    for ctx in contexts:
        if ctx.estimated_fmv <= 0:
            continue
        bin_p, auc, lo, hi, profit, roi, days, rec, factors = score_listing(ctx)
        session.add(
            P71ListingRecommendationItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                inventory_copy_id=ctx.copy_id,
                title=ctx.title,
                suggested_bin=bin_p,
                suggested_auction_start=auc,
                expected_sale_low=lo,
                expected_sale_high=hi,
                expected_profit=profit,
                expected_roi_pct=roi,
                expected_days_to_sell=days,
                listing_recommendation=rec,
                factors_json=factors,
            )
        )
        count += 1
    snap.total_items = count
    session.add(snap)
    session.flush()
    return snap
