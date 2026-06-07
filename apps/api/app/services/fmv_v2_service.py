"""P90-02 FMV Intelligence V2 engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy
from app.models.p89_market_price_snapshot import P89MarketPriceSnapshot
from app.models.p90_fmv_snapshot import P90FmvSnapshot, utc_now
from app.services.fmv_confidence_service import score_fmv_confidence
from app.services.fmv_trend_service import compute_trend_score
from app.services.market_price_engine import compute_market_price
from app.services.p89_market_pricing_service import (
    _MarketBundle,
    _identity_from_metadata,
    _listing_confidence_score,
    _norm,
    _spread_ratio,
    gather_market_bundles,
)
from app.services.premium_price_engine import compute_premium_price
from app.services.quick_sale_pricing import compute_quick_sale_price
from app.services.sales_velocity_service import classify_sales_velocity


@dataclass(frozen=True)
class FmvV2Display:
    quick_sale_value: float
    market_value: float
    premium_value: float
    valuation_confidence: str
    trend_direction: str
    trend_score: float
    sales_velocity: str
    valuation_source: str
    listing_count: int
    marketplace_count: int


def _legacy_fmv_for_key(session: Session, *, owner_user_id: int, series: str, issue: str, variant: str) -> float:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.hold_status != "sold")
        ).all()
    )
    values: list[float] = []
    for copy in copies:
        ident = _identity_from_metadata(copy.metadata_identity_key)
        if _norm(ident.series) != _norm(series):
            continue
        if _norm(ident.issue_number) != _norm(issue):
            continue
        if variant and _norm(ident.variant) != _norm(variant):
            continue
        fmv = float(copy.current_fmv or 0)
        if fmv > 0:
            values.append(fmv)
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _historical_consistency(session: Session, *, owner_user_id: int, series: str, issue: str, variant: str) -> float | None:
    rows = list(
        session.exec(
            select(P90FmvSnapshot)
            .where(P90FmvSnapshot.owner_user_id == owner_user_id)
            .where(P90FmvSnapshot.series == _norm(series))
            .where(P90FmvSnapshot.issue_number == _norm(issue))
            .where(P90FmvSnapshot.variant == _norm(variant))
            .order_by(col(P90FmvSnapshot.snapshot_date).desc())
            .limit(5)
        ).all()
    )
    if len(rows) < 2:
        return None
    markets = [float(r.market_value) for r in rows if r.market_value > 0]
    if len(markets) < 2:
        return None
    avg = sum(markets) / len(markets)
    if avg <= 0:
        return None
    spread = (max(markets) - min(markets)) / avg
    return max(0.0, min(1.0, 1.0 - spread))


def _prior_market_value(
    session: Session,
    *,
    owner_user_id: int,
    series: str,
    issue: str,
    variant: str,
    before: date,
) -> float | None:
    row = session.exec(
        select(P90FmvSnapshot)
        .where(P90FmvSnapshot.owner_user_id == owner_user_id)
        .where(P90FmvSnapshot.series == _norm(series))
        .where(P90FmvSnapshot.issue_number == _norm(issue))
        .where(P90FmvSnapshot.variant == _norm(variant))
        .where(P90FmvSnapshot.snapshot_date < before)
        .order_by(col(P90FmvSnapshot.snapshot_date).desc())
        .limit(1)
    ).first()
    if row is not None and row.market_value > 0:
        return float(row.market_value)
    p89 = session.exec(
        select(P89MarketPriceSnapshot)
        .where(P89MarketPriceSnapshot.owner_user_id == owner_user_id)
        .where(P89MarketPriceSnapshot.series == _norm(series))
        .where(P89MarketPriceSnapshot.issue_number == _norm(issue))
        .where(P89MarketPriceSnapshot.variant == _norm(variant))
        .where(P89MarketPriceSnapshot.snapshot_date < before)
        .order_by(col(P89MarketPriceSnapshot.snapshot_date).desc())
        .limit(1)
    ).first()
    if p89 is not None and p89.market_price > 0:
        return float(p89.market_price)
    return None


def compute_fmv_v2_for_bundle(
    session: Session,
    *,
    owner_user_id: int,
    bundle: _MarketBundle,
    snapshot_date: date,
) -> P90FmvSnapshot | None:
    prices = bundle.active_prices
    legacy = _legacy_fmv_for_key(
        session,
        owner_user_id=owner_user_id,
        series=bundle.key.series,
        issue=bundle.key.issue_number,
        variant=bundle.key.variant,
    )
    if not prices and legacy <= 0 and bundle.sold_count <= 0:
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

    source = "LEGACY"
    if len(prices) >= 3 and market > 0:
        source = "MARKETPLACE"
    elif len(prices) >= 1 and market > 0 and legacy > 0:
        source = "HYBRID"
        market = round(market * 0.7 + legacy * 0.3, 2)
        quick = round(quick * 0.7 + legacy * 0.28, 2)
        premium = round(premium * 0.7 + legacy * 0.35, 2)
    elif market <= 0 and legacy > 0:
        market = legacy
        quick = round(legacy * 0.85, 2)
        premium = round(legacy * 1.12, 2)
    elif market <= 0:
        return None

    hist = _historical_consistency(
        session,
        owner_user_id=owner_user_id,
        series=bundle.key.series,
        issue=bundle.key.issue_number,
        variant=bundle.key.variant,
    )
    confidence = score_fmv_confidence(
        listing_count=len(prices),
        marketplace_count=len(bundle.marketplaces),
        price_spread_ratio=spread,
        latest_observation_at=bundle.latest_at,
        sales_velocity=velocity,
        historical_consistency=hist,
    )
    prior = _prior_market_value(
        session,
        owner_user_id=owner_user_id,
        series=bundle.key.series,
        issue=bundle.key.issue_number,
        variant=bundle.key.variant,
        before=snapshot_date,
    )
    trend_dir, trend_score = compute_trend_score(current_value=float(market), prior_value=prior)

    return P90FmvSnapshot(
        owner_user_id=owner_user_id,
        series=bundle.key.series,
        issue_number=bundle.key.issue_number,
        variant=bundle.key.variant,
        quick_sale_value=round(float(quick or market), 2),
        market_value=round(float(market), 2),
        premium_value=round(float(premium or market), 2),
        valuation_confidence=confidence,
        trend_direction=trend_dir,
        trend_score=trend_score,
        sales_velocity=velocity,
        listing_count=len(prices),
        marketplace_count=len(bundle.marketplaces),
        valuation_source=source,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )


def generate_fmv_v2_snapshots(
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
        "snapshots_updated": 0,
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
    }
    for bundle in bundles.values():
        row = compute_fmv_v2_for_bundle(session, owner_user_id=owner_user_id, bundle=bundle, snapshot_date=day)
        if row is None:
            continue
        existing = session.exec(
            select(P90FmvSnapshot)
            .where(P90FmvSnapshot.owner_user_id == owner_user_id)
            .where(P90FmvSnapshot.series == row.series)
            .where(P90FmvSnapshot.issue_number == row.issue_number)
            .where(P90FmvSnapshot.variant == row.variant)
            .where(P90FmvSnapshot.snapshot_date == day)
        ).first()
        if dry_run:
            counts["snapshots_created"] += 1 if existing is None else 0
            counts["snapshots_updated"] += 1 if existing is not None else 0
        elif existing is None:
            session.add(row)
            counts["snapshots_created"] += 1
        else:
            for field in (
                "quick_sale_value",
                "market_value",
                "premium_value",
                "valuation_confidence",
                "trend_direction",
                "trend_score",
                "sales_velocity",
                "listing_count",
                "marketplace_count",
                "valuation_source",
            ):
                setattr(existing, field, getattr(row, field))
            session.add(existing)
            counts["snapshots_updated"] += 1
        conf = row.valuation_confidence
        if conf == "HIGH":
            counts["high_confidence"] += 1
        elif conf == "MEDIUM":
            counts["medium_confidence"] += 1
        else:
            counts["low_confidence"] += 1
    if not dry_run:
        session.flush()
    return counts


def lookup_latest_fmv_v2(
    session: Session,
    *,
    owner_user_id: int,
    series: str,
    issue_number: str,
    variant: str = "",
) -> P90FmvSnapshot | None:
    from app.services.p90_safe_reads import p90_safe_call

    return p90_safe_call(
        session,
        lambda: session.exec(
            select(P90FmvSnapshot)
            .where(P90FmvSnapshot.owner_user_id == owner_user_id)
            .where(P90FmvSnapshot.series == _norm(series))
            .where(P90FmvSnapshot.issue_number == _norm(issue_number))
            .where(P90FmvSnapshot.variant == _norm(variant))
            .order_by(col(P90FmvSnapshot.snapshot_date).desc(), col(P90FmvSnapshot.id).desc())
            .limit(1)
        ).first(),
        default=None,
        label="lookup_latest_fmv_v2",
    )


def lookup_fmv_v2_display(
    session: Session,
    *,
    owner_user_id: int,
    series: str,
    issue_number: str,
    variant: str = "",
) -> FmvV2Display | None:
    row = lookup_latest_fmv_v2(
        session,
        owner_user_id=owner_user_id,
        series=series,
        issue_number=issue_number,
        variant=variant,
    )
    if row is None:
        from app.services.p89_market_pricing_service import lookup_latest_snapshot

        p89 = lookup_latest_snapshot(
            session,
            owner_user_id=owner_user_id,
            series=series,
            issue_number=issue_number,
            variant=variant,
        )
        if p89 is None:
            legacy = _legacy_fmv_for_key(
                session,
                owner_user_id=owner_user_id,
                series=series,
                issue=issue_number,
                variant=variant,
            )
            if legacy <= 0:
                return None
            return FmvV2Display(
                quick_sale_value=round(legacy * 0.85, 2),
                market_value=legacy,
                premium_value=round(legacy * 1.12, 2),
                valuation_confidence="LOW",
                trend_direction="FLAT",
                trend_score=0.0,
                sales_velocity="NORMAL",
                valuation_source="LEGACY",
                listing_count=0,
                marketplace_count=0,
            )
        return FmvV2Display(
            quick_sale_value=float(p89.quick_sale_price),
            market_value=float(p89.market_price),
            premium_value=float(p89.premium_price),
            valuation_confidence=p89.pricing_confidence,
            trend_direction=p89.trend_direction,
            trend_score=0.0,
            sales_velocity=p89.sales_velocity,
            valuation_source="MARKETPLACE",
            listing_count=p89.listing_count,
            marketplace_count=0,
        )
    return FmvV2Display(
        quick_sale_value=float(row.quick_sale_value),
        market_value=float(row.market_value),
        premium_value=float(row.premium_value),
        valuation_confidence=row.valuation_confidence,
        trend_direction=row.trend_direction,
        trend_score=float(row.trend_score),
        sales_velocity=row.sales_velocity,
        valuation_source=row.valuation_source,
        listing_count=row.listing_count,
        marketplace_count=row.marketplace_count,
    )


def lookup_fmv_v2_for_copy(session: Session, *, owner_user_id: int, copy: InventoryCopy) -> FmvV2Display | None:
    ident = _identity_from_metadata(copy.metadata_identity_key)
    series = ident.series or "Unknown"
    return lookup_fmv_v2_display(
        session,
        owner_user_id=owner_user_id,
        series=series,
        issue_number=ident.issue_number,
        variant=ident.variant,
    )


def latest_snapshots_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 500,
) -> list[P90FmvSnapshot]:
    from app.services.p90_safe_reads import p90_safe_call

    def _load() -> list[P90FmvSnapshot]:
        rows = list(
            session.exec(
                select(P90FmvSnapshot)
                .where(P90FmvSnapshot.owner_user_id == owner_user_id)
                .order_by(col(P90FmvSnapshot.snapshot_date).desc(), col(P90FmvSnapshot.id).desc())
            ).all()
        )
        seen: set[tuple[str, str, str]] = set()
        latest: list[P90FmvSnapshot] = []
        for row in rows:
            key = (row.series, row.issue_number, row.variant)
            if key in seen:
                continue
            seen.add(key)
            latest.append(row)
            if len(latest) >= limit:
                break
        return latest

    return p90_safe_call(session, _load, default=[], label="latest_fmv_v2_snapshots")
