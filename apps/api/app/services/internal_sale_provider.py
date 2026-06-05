"""P68-06 Internal Sales Ledger — INTERNAL_SALE observations from owner exits."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.live_sale_workflows import LiveSaleQueueItem
from app.models.market_pricing_engine import PROVIDER_INTERNAL_SALE, P68MarketPriceObservation, utc_now
from app.services.sell_candidate_engine import _split_identity_key


SOLD_HOLD_STATUSES = frozenset({"sold", "sold_internal"})


def _money(v: Decimal | float | None) -> float:
    if v is None:
        return 0.0
    return float(v)


def ingest_internal_sale_observations(session: Session, *, owner_user_id: int) -> list[P68MarketPriceObservation]:
    """Materialize internal sale rows (does not mutate inventory current_fmv)."""
    created: list[P68MarketPriceObservation] = []
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
    live_sales = {
        int(r.inventory_item_id): r
        for r in session.exec(
            select(LiveSaleQueueItem).where(LiveSaleQueueItem.item_status == "SOLD")
        ).all()
        if r.actual_sale_price is not None
    }

    for copy in copies:
        if (copy.hold_status or "") not in SOLD_HOLD_STATUSES:
            continue
        copy_id = int(copy.id or 0)
        live = live_sales.get(copy_id)
        total = _money(live.actual_sale_price) if live else 0.0
        if total <= 0:
            continue
        pub, series, issue, variant = _split_identity_key(copy.metadata_identity_key)
        title = series or (copy.metadata_identity_key or f"Copy {copy_id}")
        realized = total - _money(copy.acquisition_cost)
        listing_key = f"internal-copy-{copy_id}"
        if session.exec(
            select(P68MarketPriceObservation.id)
            .where(P68MarketPriceObservation.owner_user_id == owner_user_id)
            .where(P68MarketPriceObservation.external_listing_id == listing_key)
        ).first():
            continue
        obs = P68MarketPriceObservation(
            owner_user_id=owner_user_id,
            provider=PROVIDER_INTERNAL_SALE,
            external_listing_id=listing_key,
            observed_at=utc_now(),
            sale_date=date.today(),
            title=title,
            publisher=pub,
            issue_number=issue,
            series_key=f"{pub}|{title}|{issue}".lower(),
            variant_label=variant or None,
            raw_or_graded="graded" if (copy.grade_status or "raw") != "raw" else "raw",
            grade=copy.grade_status if (copy.grade_status or "raw") != "raw" else None,
            sold_price=total,
            shipping_price=0.0,
            total_price=total,
            confidence=0.92,
            inventory_copy_id=copy_id,
            metadata_json={
                "realized_gain": round(realized, 2),
                "source": "internal_sales_ledger",
                "hold_status": copy.hold_status,
            },
        )
        session.add(obs)
        created.append(obs)

    session.flush()
    return created
