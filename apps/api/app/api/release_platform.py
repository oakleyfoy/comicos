from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.release_platform import ContinueRunPlanListResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.continue_run_planning import build_continue_run_planning
from app.services.future_buy_queue import build_future_buy_queue
from app.services.opportunity_intelligence import build_opportunity_intelligence
from app.services.release_budget_planner import build_budget_forecast
from app.services.release_horizon_engine import build_release_horizons
from app.services.release_opportunity_dashboard import build_release_opportunity_dashboard

release_platform_v1_router = APIRouter(prefix="/api/v1", tags=["Release Platform API v1 (P50-04)"])


def attach_release_platform_layer(app: FastAPI) -> None:
    app.include_router(release_platform_v1_router)


@release_platform_v1_router.get("/release-platform/horizons", response_model=ScanApiV1Envelope)
def v1_release_platform_horizons(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_release_horizons(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_v1_router.get("/release-platform/opportunities", response_model=ScanApiV1Envelope)
def v1_release_platform_opportunities(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_opportunity_intelligence(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_v1_router.get("/release-platform/future-buy-queue", response_model=ScanApiV1Envelope)
def v1_release_platform_future_buy_queue(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_future_buy_queue(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_v1_router.get("/release-platform/run-planning", response_model=ScanApiV1Envelope)
def v1_release_platform_run_planning(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = ContinueRunPlanListResponse(
        items=build_continue_run_planning(session, owner_user_id=int(current_user.id))
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_v1_router.get("/release-platform/budget", response_model=ScanApiV1Envelope)
def v1_release_platform_budget(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_budget_forecast(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_v1_router.get("/release-platform/ratio-variants", response_model=ScanApiV1Envelope)
def v1_release_platform_ratio_variants(
    limit: int = 20,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.schemas.release_intelligence import ReleaseVariantListResponse
    from app.services.release_variant_metrics import list_top_ratio_variants

    items = list_top_ratio_variants(session, owner_user_id=int(current_user.id), limit=limit)
    body = ReleaseVariantListResponse(items=items, total_items=len(items), limit=limit, offset=0)
    from app.schemas.scan_api_v1 import wrap_standard_list

    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_platform_v1_router.get("/release-platform/new-variants", response_model=ScanApiV1Envelope)
def v1_release_platform_new_variants(
    limit: int = 20,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.schemas.release_intelligence import ReleaseVariantListResponse
    from app.services.release_variant_metrics import list_recent_variants
    from app.schemas.scan_api_v1 import wrap_standard_list

    items = list_recent_variants(session, owner_user_id=int(current_user.id), limit=limit)
    body = ReleaseVariantListResponse(items=items, total_items=len(items), limit=limit, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_platform_v1_router.get("/release-platform/dashboard", response_model=ScanApiV1Envelope)
def v1_release_platform_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_release_opportunity_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
