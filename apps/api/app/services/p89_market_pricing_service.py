"""P89-02 Market Pricing Intelligence — aggregates stored P88/P82 marketplace data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.models.p89_market_price_snapshot import P89MarketPriceSnapshot, utc_now
from app.services.market_price_engine import compute_market_price
from app.services.market_trend_service import compute_trend_direction
from app.services.premium_price_engine import compute_premium_price
from app.services.pricing_confidence_service import score_pricing_confidence
from app.services.quick_sale_pricing import compute_quick_sale_price
from app.services.sales_velocity_service import classify_sales_velocity, velocity_display_label


@dataclass
class _IdentityKey:
    series: str
    issue_number: str
    variant: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.series, self.issue_number, self.variant)


@dataclass
class _MarketBundle:
    key: _IdentityKey
    active_prices: list[float] = field(default_factory=list)
    confidence_labels: list[str] = field(default_factory=list)
    marketplaces: set[str] = field(default_factory=set)
    sold_count: int = 0
    latest_at: datetime | None = None

    def add_active(self, price: float, *, marketplace: str, confidence: str, observed_at: datetime | None) -> None:
        if price <= 0:
            return
        self.active_prices.append(round(price, 2))
        self.confidence_labels.append(confidence or "MEDIUM")
        if marketplace:
            self.marketplaces.add(marketplace.upper())
        if observed_at is not None:
            if self.latest_at is None or observed_at > self.latest_at:
                self.latest_at = observed_at


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _identity_from_metadata(key: str | None) -> _IdentityKey:
    if not key:
        return _IdentityKey("", "", "")
    parts = key.split("|")
    while len(parts) < 3:
        parts.append("")
    return _IdentityKey(_norm(parts[1]), _norm(parts[2]), "")


def _listing_confidence_score(label: str) -> float:
    return {"HIGH": 1.0, "MEDIUM": 0.75, "LOW": 0.5}.get(label.upper(), 0.65)


def _spread_ratio(prices: list[float]) -> float:
    if len(prices) < 2:
        return 0.0
    low, high = min(prices), max(prices)
    avg = sum(prices) / len(prices)
    if avg <= 0:
        return 0.0
    return (high - low) / avg


def gather_market_bundles(session: Session, *, owner_user_id: int) -> dict[tuple[str, str, str], _MarketBundle]:
    bundles: dict[tuple[str, str, str], _MarketBundle] = {}

    def bucket(key: _IdentityKey) -> _MarketBundle:
        t = key.as_tuple()
        if t not in bundles:
            bundles[t] = _MarketBundle(key=key)
        return bundles[t]

    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.hold_status != "sold")
        ).all()
    )
    for copy in copies:
        bucket(_identity_from_metadata(copy.metadata_identity_key))

    opp_by_id: dict[int, MarketplaceAcquisitionOpportunity] = {}
    for opp in session.exec(
        select(MarketplaceAcquisitionOpportunity).where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
    ).all():
        if opp.id is not None:
            opp_by_id[int(opp.id)] = opp
        key = _IdentityKey(_norm(opp.series), _norm(opp.issue), _norm(opp.variant))
        if key.series or key.issue_number:
            b = bucket(key)
            total = float(opp.asking_price or 0)
            if total > 0:
                b.add_active(total, marketplace=opp.marketplace, confidence="MEDIUM", observed_at=opp.updated_at)

    listings = list(
        session.exec(
            select(P88MarketplaceListing).where(P88MarketplaceListing.owner_user_id == owner_user_id)
        ).all()
    )
    for row in listings:
        opp = opp_by_id.get(int(row.opportunity_id or 0)) if row.opportunity_id else None
        if opp is not None:
            key = _IdentityKey(_norm(opp.series), _norm(opp.issue), _norm(opp.variant))
        else:
            key = _IdentityKey(_norm(row.title), "", "")
        b = bucket(key)
        total_price = float(row.price or 0) + float(row.shipping_cost or 0)
        observed = row.last_verified_at or row.updated_at
        if row.is_active and row.health_status == "ACTIVE":
            b.add_active(
                total_price,
                marketplace=row.marketplace,
                confidence=row.listing_confidence or "MEDIUM",
                observed_at=observed,
            )
        else:
            b.sold_count += 1

    return bundles


def build_snapshot_row(
    session: Session,
    *,
    owner_user_id: int,
    bundle: _MarketBundle,
    snapshot_date: date,
) -> P89MarketPriceSnapshot | None:
    prices = bundle.active_prices
    if not prices and bundle.sold_count <= 0:
        return None

    spread = _spread_ratio(prices) if prices else 1.0
    velocity = classify_sales_velocity(
        listing_count=len(prices),
        sold_count=bundle.sold_count,
        price_spread_ratio=spread,
    )
    conf_scores = [_listing_confidence_score(c) for c in bundle.confidence_labels]
    market = compute_market_price(active_prices=prices, listing_confidence_scores=conf_scores)
    quick = compute_quick_sale_price(
        active_prices=prices or ([market] if market > 0 else []),
        listing_count=len(prices),
        sales_velocity=velocity,
    )
    premium = compute_premium_price(
        active_prices=prices or ([market] if market > 0 else []),
        listing_count=len(prices),
        market_price=market or quick,
    )
    confidence = score_pricing_confidence(
        listing_count=len(prices),
        marketplace_sources=len(bundle.marketplaces),
        price_spread_ratio=spread,
        latest_observation_at=bundle.latest_at,
    )
    low = min(prices) if prices else market
    high = max(prices) if prices else market
    avg = sum(prices) / len(prices) if prices else market

    prior = session.exec(
        select(P89MarketPriceSnapshot)
        .where(P89MarketPriceSnapshot.owner_user_id == owner_user_id)
        .where(P89MarketPriceSnapshot.series == bundle.key.series)
        .where(P89MarketPriceSnapshot.issue_number == bundle.key.issue_number)
        .where(P89MarketPriceSnapshot.variant == bundle.key.variant)
        .where(P89MarketPriceSnapshot.snapshot_date < snapshot_date)
        .order_by(col(P89MarketPriceSnapshot.snapshot_date).desc())
        .limit(1)
    ).first()
    prior_avg = float(prior.price_average) if prior else None
    trend = compute_trend_direction(current_average=float(avg or 0), prior_average=prior_avg)

    return P89MarketPriceSnapshot(
        owner_user_id=owner_user_id,
        series=bundle.key.series,
        issue_number=bundle.key.issue_number,
        variant=bundle.key.variant,
        quick_sale_price=quick,
        market_price=market or quick,
        premium_price=premium or market or quick,
        pricing_confidence=confidence,
        sales_velocity=velocity,
        listing_count=len(prices),
        sold_count=bundle.sold_count,
        price_low=round(float(low or 0), 2),
        price_high=round(float(high or 0), 2),
        price_average=round(float(avg or 0), 2),
        trend_direction=trend,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )


def generate_market_price_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    day = snapshot_date or date.today()
    bundles = gather_market_bundles(session, owner_user_id=owner_user_id)
    counts = {
        "snapshots_created": 0,
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "updated": 0,
    }
    for bundle in bundles.values():
        if not bundle.active_prices and bundle.sold_count <= 0:
            continue
        row = build_snapshot_row(session, owner_user_id=owner_user_id, bundle=bundle, snapshot_date=day)
        if row is None:
            continue
        if dry_run:
            counts["snapshots_created"] += 1
        else:
            existing = session.exec(
                select(P89MarketPriceSnapshot)
                .where(P89MarketPriceSnapshot.owner_user_id == owner_user_id)
                .where(P89MarketPriceSnapshot.series == row.series)
                .where(P89MarketPriceSnapshot.issue_number == row.issue_number)
                .where(P89MarketPriceSnapshot.variant == row.variant)
                .where(P89MarketPriceSnapshot.snapshot_date == day)
            ).first()
            if existing is None:
                session.add(row)
                counts["snapshots_created"] += 1
            else:
                existing.quick_sale_price = row.quick_sale_price
                existing.market_price = row.market_price
                existing.premium_price = row.premium_price
                existing.pricing_confidence = row.pricing_confidence
                existing.sales_velocity = row.sales_velocity
                existing.listing_count = row.listing_count
                existing.sold_count = row.sold_count
                existing.price_low = row.price_low
                existing.price_high = row.price_high
                existing.price_average = row.price_average
                existing.trend_direction = row.trend_direction
                session.add(existing)
                counts["updated"] += 1
        conf = row.pricing_confidence
        if conf == "HIGH":
            counts["high_confidence"] += 1
        elif conf == "MEDIUM":
            counts["medium_confidence"] += 1
        else:
            counts["low_confidence"] += 1
    if not dry_run:
        session.flush()
    return counts


def latest_snapshots_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 500,
) -> list[P89MarketPriceSnapshot]:
    rows = list(
        session.exec(
            select(P89MarketPriceSnapshot)
            .where(P89MarketPriceSnapshot.owner_user_id == owner_user_id)
            .order_by(col(P89MarketPriceSnapshot.snapshot_date).desc(), col(P89MarketPriceSnapshot.id).desc())
        ).all()
    )
    seen: set[tuple[str, str, str]] = set()
    latest: list[P89MarketPriceSnapshot] = []
    for row in rows:
        key = (row.series, row.issue_number, row.variant)
        if key in seen:
            continue
        seen.add(key)
        latest.append(row)
        if len(latest) >= limit:
            break
    return latest


def lookup_latest_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    series: str,
    issue_number: str,
    variant: str = "",
) -> P89MarketPriceSnapshot | None:
    return session.exec(
        select(P89MarketPriceSnapshot)
        .where(P89MarketPriceSnapshot.owner_user_id == owner_user_id)
        .where(P89MarketPriceSnapshot.series == _norm(series))
        .where(P89MarketPriceSnapshot.issue_number == _norm(issue_number))
        .where(P89MarketPriceSnapshot.variant == _norm(variant))
        .order_by(col(P89MarketPriceSnapshot.snapshot_date).desc(), col(P89MarketPriceSnapshot.id).desc())
        .limit(1)
    ).first()


def build_portfolio_pricing_totals(session: Session, *, owner_user_id: int) -> dict[str, float]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.hold_status != "sold")
        ).all()
    )
    quick_total = 0.0
    market_total = 0.0
    premium_total = 0.0
    for copy in copies:
        ident = _identity_from_metadata(copy.metadata_identity_key)
        snap = lookup_latest_snapshot(
            session,
            owner_user_id=owner_user_id,
            series=ident.series,
            issue_number=ident.issue_number,
            variant=ident.variant,
        )
        if snap is None:
            continue
        qty = 1
        quick_total += float(snap.quick_sale_price) * qty
        market_total += float(snap.market_price) * qty
        premium_total += float(snap.premium_price) * qty
    return {
        "quick_liquidation_total": round(quick_total, 2),
        "market_value_total": round(market_total, 2),
        "premium_value_total": round(premium_total, 2),
    }


def build_market_pricing_briefing_summary(session: Session, *, owner_user_id: int) -> dict[str, str | None]:
    rows = latest_snapshots_for_owner(session, owner_user_id=owner_user_id, limit=200)
    if not rows:
        return {
            "highest_value_book": None,
            "fastest_seller": None,
            "largest_trend_increase": None,
        }

    def title(row: P89MarketPriceSnapshot) -> str:
        if row.issue_number:
            return f"{row.series} #{row.issue_number}".strip()
        return row.series or "Comic"

    highest = max(rows, key=lambda r: r.market_price)
    fastest = max(rows, key=lambda r: ({"VERY_FAST": 5, "FAST": 4, "NORMAL": 3, "SLOW": 2, "VERY_SLOW": 1}.get(r.sales_velocity, 0), r.market_price))
    up_rows = [r for r in rows if r.trend_direction == "UP"]
    trend_pick = max(up_rows, key=lambda r: r.price_average) if up_rows else None
    return {
        "highest_value_book": title(highest),
        "fastest_seller": title(fastest),
        "largest_trend_increase": title(trend_pick) if trend_pick else None,
    }


def snapshot_to_read_dict(row: P89MarketPriceSnapshot) -> dict:
    return {
        "id": int(row.id or 0),
        "owner_user_id": int(row.owner_user_id),
        "series": row.series,
        "issue_number": row.issue_number,
        "variant": row.variant,
        "display_title": f"{row.series} #{row.issue_number}".strip() if row.issue_number else row.series,
        "quick_sale_price": float(row.quick_sale_price),
        "market_price": float(row.market_price),
        "premium_price": float(row.premium_price),
        "pricing_confidence": row.pricing_confidence,
        "sales_velocity": row.sales_velocity,
        "sales_velocity_label": velocity_display_label(row.sales_velocity),
        "listing_count": int(row.listing_count),
        "sold_count": int(row.sold_count),
        "price_low": float(row.price_low),
        "price_high": float(row.price_high),
        "price_average": float(row.price_average),
        "trend_direction": row.trend_direction,
        "snapshot_date": row.snapshot_date.isoformat(),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
