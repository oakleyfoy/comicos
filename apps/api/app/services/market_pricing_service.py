"""P66-03 Market pricing — provider abstraction (stub; no live scraping)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.models.variant_market_intelligence import MarketPriceObservation, MarketPriceSnapshot, utc_now
from app.services.buy_queue_service import get_latest_buy_queue_snapshot, list_buy_queue_items

PROVIDER_STUB = "STUB"


def get_latest_market_price_snapshot(session: Session, *, owner_user_id: int) -> MarketPriceSnapshot | None:
    return session.exec(
        select(MarketPriceSnapshot)
        .where(MarketPriceSnapshot.owner_user_id == owner_user_id)
        .order_by(MarketPriceSnapshot.generated_at.desc(), MarketPriceSnapshot.id.desc())
    ).first()


def list_market_observations(session: Session, *, snapshot_id: int, limit: int = 500) -> list[MarketPriceObservation]:
    return list(
        session.exec(
            select(MarketPriceObservation)
            .where(MarketPriceObservation.snapshot_id == snapshot_id)
            .order_by(MarketPriceObservation.fmv.desc(), MarketPriceObservation.id.asc())
            .limit(limit)
        ).all()
    )


def _liquidity_label(pull: int, want: int) -> str:
    if pull >= 400 or want >= 600:
        return "HIGH"
    if pull >= 120 or want >= 200:
        return "MEDIUM"
    return "LOW"


def _stub_fmv(*, base_price: float, variant: ExternalCatalogVariant, pull: int, want: int) -> tuple[float, str, str, float]:
    name = (variant.variant_name or "").lower()
    mult = 1.0
    if "foil" in name:
        mult += 0.18
    if variant.ratio_value and variant.ratio_value >= 25:
        mult += 0.12
    if "virgin" in name or "sketch" in name:
        mult += 0.08
    fmv = round(max(base_price, float(variant.price or base_price)) * mult, 2)
    trend = "RISING" if pull >= 300 else "STABLE"
    liq = _liquidity_label(pull, want)
    conf = min(0.95, 0.45 + (pull * 0.0004) + (want * 0.0003))
    return fmv, trend, liq, round(conf, 3)


def build_market_prices(session: Session, *, owner_user_id: int) -> MarketPriceSnapshot:
    snap = MarketPriceSnapshot(
        owner_user_id=owner_user_id,
        provider=PROVIDER_STUB,
        total_observations=0,
        metadata_json={"sources_future": ["ebay_sold", "gocollect", "covrprice", "heritage", "comicpriceguide"]},
    )
    session.add(snap)
    session.flush()

    issue_ids: set[int] = set()
    bq = get_latest_buy_queue_snapshot(session, owner_user_id=owner_user_id)
    if bq:
        items, _ = list_buy_queue_items(session, snapshot_id=int(bq.id or 0), limit=100)
        for row in items:
            if row.external_catalog_issue_id:
                issue_ids.add(int(row.external_catalog_issue_id))

    count = 0
    for iid in issue_ids:
        issue = session.get(ExternalCatalogIssue, iid)
        if issue is None:
            continue
        pull = int(issue.pull_count or 0)
        want = int(issue.want_count or 0)
        base = float(issue.price or 4.99)
        variants = list(
            session.exec(select(ExternalCatalogVariant).where(ExternalCatalogVariant.external_issue_id == iid)).all()
        )
        if not variants:
            continue
        for var in variants:
            fmv, trend, liq, conf = _stub_fmv(base_price=base, variant=var, pull=pull, want=want)
            session.add(
                MarketPriceObservation(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    external_catalog_issue_id=iid,
                    external_catalog_variant_id=int(var.id or 0),
                    fmv=fmv,
                    price_trend=trend,
                    liquidity=liq,
                    market_confidence=conf,
                    source_key="stub",
                    provenance_json={"pull_count": pull, "want_count": want},
                )
            )
            count += 1

    snap.total_observations = count
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
