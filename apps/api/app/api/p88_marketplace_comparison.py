"""P88-04 marketplace comparison, coverage, and diagnostics APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.schemas.p88_marketplace_comparison import (
    BestBuyRecommendationRead,
    MarketplaceComparisonRead,
    MarketplaceComparisonRowRead,
    MarketplaceCoverageRead,
    MarketplaceDiagnosticsRead,
    MarketplaceRegistryEntryRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.marketplace.best_buy_service import recommend_best_buy
from app.services.marketplace.listing_health_service import is_listing_displayable
from app.services.marketplace.marketplace_comparison_service import compare_opportunity_listings
from app.services.marketplace.marketplace_coverage_service import build_marketplace_coverage
from app.services.marketplace.marketplace_diagnostics_service import build_marketplace_diagnostics
from app.services.marketplace.marketplace_registry import MARKETPLACE_REGISTRY, list_supported_marketplace_codes
from app.services.ops_access import is_ops_admin_user

p88_comparison_router = APIRouter(tags=["Marketplace Comparison (P88-04)"])


def attach_p88_marketplace_comparison_layer(app: FastAPI) -> None:
    app.include_router(p88_comparison_router)


def _comparison_read(result) -> MarketplaceComparisonRead:
    return MarketplaceComparisonRead(
        best_marketplace=result.best_marketplace,
        best_marketplace_name=result.best_marketplace_name,
        best_price=result.best_price,
        best_total_cost=result.best_total_cost,
        savings_vs_highest=result.savings_vs_highest,
        rankings=[
            MarketplaceComparisonRowRead(
                marketplace=row.marketplace,
                marketplace_name=row.marketplace_name,
                price=row.price,
                shipping=row.shipping,
                overall_cost=row.overall_cost,
                availability_status=row.availability_status,
                listing_confidence=row.listing_confidence,
                listing_count=row.listing_count,
                is_best=row.is_best,
            )
            for row in result.rankings
        ],
    )


@p88_comparison_router.get("/api/v1/buy-opportunities/{opportunity_id}/marketplace-comparison", response_model=ScanApiV1Envelope)
def v1_opportunity_marketplace_comparison(
    opportunity_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    result = compare_opportunity_listings(
        session,
        owner_user_id=int(current_user.id),
        opportunity_id=opportunity_id,
    )
    listings = session.exec(
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.owner_user_id == int(current_user.id))
        .where(P88MarketplaceListing.opportunity_id == opportunity_id)
    ).all()
    displayable = [row for row in listings if is_listing_displayable(row)]
    best_buy = recommend_best_buy(displayable)
    body = {
        "comparison": _comparison_read(result),
        "best_buy": BestBuyRecommendationRead(
            marketplace=best_buy.marketplace,
            marketplace_name=best_buy.marketplace_name,
            price=best_buy.price,
            shipping=best_buy.shipping,
            total_cost=best_buy.total_cost,
            reason=best_buy.reason,
            listing_confidence=best_buy.listing_confidence,
        ),
    }
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_comparison_router.get("/api/v1/marketplace/registry", response_model=ScanApiV1Envelope)
def v1_marketplace_registry(
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = []
    for code in list_supported_marketplace_codes(include_other=True):
        row = MARKETPLACE_REGISTRY[code]
        items.append(
            MarketplaceRegistryEntryRead(
                code=row.code,
                display_name=row.display_name,
                supports_search=row.supports_search,
                supports_listing_lookup=row.supports_listing_lookup,
                supports_price_tracking=row.supports_price_tracking,
                supports_refresh=row.supports_refresh,
            )
        )
    return wrap_object({"items": items}, owner_user_id=int(current_user.id))


@p88_comparison_router.get("/api/v1/admin/marketplace-coverage", response_model=ScanApiV1Envelope)
def v1_admin_marketplace_coverage(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    if not is_ops_admin_user(current_user, settings):
        raise HTTPException(status_code=403, detail="Admin access required.")
    body: MarketplaceCoverageRead = build_marketplace_coverage(session)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_comparison_router.get("/api/v1/admin/marketplace-diagnostics", response_model=ScanApiV1Envelope)
def v1_admin_marketplace_diagnostics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    if not is_ops_admin_user(current_user, settings):
        raise HTTPException(status_code=403, detail="Admin access required.")
    body: MarketplaceDiagnosticsRead = build_marketplace_diagnostics(session)
    return wrap_object(body, owner_user_id=int(current_user.id))
