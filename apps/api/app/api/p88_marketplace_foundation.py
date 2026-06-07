"""P88 marketplace foundation APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.p88_marketplace_foundation import (
    BuyOpportunityImportUrlPayload,
    EbayIntegrationStatusRead,
    MarketplaceImportAuditListResponse,
    MarketplaceImportUrlResponse,
    MarketplaceOpportunitySourceListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace.ebay_client import load_ebay_configuration
from app.services.marketplace_opportunity_source_service import (
    import_marketplace_url,
    list_marketplace_import_audit,
    list_opportunity_sources,
)
from app.services.ops_access import is_ops_admin_user

p88_marketplace_router = APIRouter(tags=["Marketplace Foundation (P88)"])


def attach_p88_marketplace_foundation_layer(app: FastAPI) -> None:
    app.include_router(p88_marketplace_router)


@p88_marketplace_router.post("/api/v1/buy-opportunities/import-url", response_model=ScanApiV1Envelope)
def v1_import_buy_opportunity_url(
    payload: BuyOpportunityImportUrlPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceImportUrlResponse = import_marketplace_url(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_marketplace_router.get("/api/v1/buy-opportunities/sources", response_model=ScanApiV1Envelope)
def v1_list_buy_opportunity_sources(
    opportunity_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceOpportunitySourceListResponse = list_opportunity_sources(
        session,
        owner_user_id=int(current_user.id),
        opportunity_id=opportunity_id,
        limit=limit,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p88_marketplace_router.get("/api/v1/marketplace/integration/ebay", response_model=ScanApiV1Envelope)
def v1_ebay_integration_status(
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    cfg = load_ebay_configuration(settings)
    body = EbayIntegrationStatusRead(
        status="Configured" if cfg.configured else "Not Configured",
        environment=cfg.environment,
        client_id_present=cfg.client_id_present,
        client_secret_present=cfg.client_secret_present,
        detail=cfg.message,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_marketplace_router.get("/api/v1/admin/marketplace-imports", response_model=ScanApiV1Envelope)
def v1_admin_marketplace_imports(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    if not is_ops_admin_user(current_user, settings):
        raise HTTPException(status_code=403, detail="Admin access required.")
    body: MarketplaceImportAuditListResponse = list_marketplace_import_audit(
        session,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
