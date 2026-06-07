from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p89_market_pricing import (
    P89MarketPriceSnapshotRead,
    P89MarketPricingDashboardRead,
    P89MarketPricingGenerateResponse,
    P89MarketPricingPortfolioTotalsRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.p89_market_pricing_service import (
    build_portfolio_pricing_totals,
    generate_market_price_snapshots,
    latest_snapshots_for_owner,
    snapshot_to_read_dict,
)

p89_market_pricing_router = APIRouter(prefix="/api/v1", tags=["Market Pricing Intelligence (P89-02)"])


def attach_p89_market_pricing_layer(app: FastAPI) -> None:
    app.include_router(p89_market_pricing_router)


def _read(row) -> P89MarketPriceSnapshotRead:
    return P89MarketPriceSnapshotRead(**snapshot_to_read_dict(row))


@p89_market_pricing_router.get("/market-pricing/dashboard", response_model=ScanApiV1Envelope)
def v1_market_pricing_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(8, ge=1, le=50),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    uid = int(current_user.id)
    rows = latest_snapshots_for_owner(session, owner_user_id=uid, limit=500)
    body = P89MarketPricingDashboardRead(
        highest_value_books=[_read(r) for r in sorted(rows, key=lambda x: x.market_price, reverse=True)[:limit]],
        fastest_selling_books=[
            _read(r)
            for r in sorted(
                rows,
                key=lambda x: (
                    {"VERY_FAST": 5, "FAST": 4, "NORMAL": 3, "SLOW": 2, "VERY_SLOW": 1}.get(x.sales_velocity, 0),
                    x.market_price,
                ),
                reverse=True,
            )[:limit]
        ],
        largest_price_increases=[_read(r) for r in [x for x in rows if x.trend_direction == "UP"][:limit]],
        largest_price_decreases=[_read(r) for r in [x for x in rows if x.trend_direction == "DOWN"][:limit]],
        highest_confidence_pricing=[
            _read(r)
            for r in sorted(
                rows,
                key=lambda x: ({"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(x.pricing_confidence, 0), x.market_price),
                reverse=True,
            )[:limit]
        ],
    )
    return wrap_object(body, owner_user_id=uid)


@p89_market_pricing_router.get("/market-pricing/portfolio-totals", response_model=ScanApiV1Envelope)
def v1_market_pricing_portfolio_totals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    totals = build_portfolio_pricing_totals(session, owner_user_id=int(current_user.id))
    body = P89MarketPricingPortfolioTotalsRead(**totals)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p89_market_pricing_router.post("/market-pricing/generate", response_model=ScanApiV1Envelope)
def v1_generate_market_pricing(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    summary = generate_market_price_snapshots(session, owner_user_id=int(current_user.id), dry_run=False)
    session.commit()
    body = P89MarketPricingGenerateResponse(
        snapshots_created=int(summary.get("snapshots_created") or 0),
        updated=int(summary.get("updated") or 0),
        high_confidence=int(summary.get("high_confidence") or 0),
        medium_confidence=int(summary.get("medium_confidence") or 0),
        low_confidence=int(summary.get("low_confidence") or 0),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
