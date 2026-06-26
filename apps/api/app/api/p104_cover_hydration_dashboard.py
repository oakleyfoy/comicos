"""P104 Cover Hydration dashboard API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.p104_cover_hydration_dashboard import (
    P104CoverHydrationDryRunRequest,
    P104CoverHydrationDryRunResponse,
    P104CoverHydrationRunRequest,
    P104CoverHydrationRunResponse,
    P104CoverHydrationStatusResponse,
)
from app.services.p104_cover_hydration_service import (
    p104_dashboard_metrics,
    run_p104_dry_run,
    run_p104_hydration,
)

p104_cover_hydration_v1_router = APIRouter(prefix="/api/v1/catalog-cover-hydration", tags=["Cover Hydration"])


def attach_p104_cover_hydration_dashboard_layer(app) -> None:
    app.include_router(p104_cover_hydration_v1_router)


def _require_enabled() -> None:
    if not get_settings().p104_cover_hydration_enabled:
        raise HTTPException(status_code=503, detail="P104 cover hydration is disabled")


@p104_cover_hydration_v1_router.get("/status", response_model=P104CoverHydrationStatusResponse)
def cover_hydration_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> P104CoverHydrationStatusResponse:
    del current_user
    _require_enabled()
    settings = get_settings()
    metrics = p104_dashboard_metrics(session)
    return P104CoverHydrationStatusResponse(
        enabled=True,
        total=int(metrics["total"]),
        complete=int(metrics["complete"]),
        failed=int(metrics["failed"]),
        skipped_no_url=int(metrics["skipped_no_url"]),
        pending=int(metrics["pending"]),
        rate_per_hour=int(metrics["rate_per_hour"]),
        eta_hours=metrics.get("eta_hours"),
        storage_root=str(metrics["storage_root"]),
        downloads_per_minute=float(settings.p104_downloads_per_minute),
        year_from=int(settings.p104_year_from),
        year_to=int(settings.p104_year_to),
        total_catalog_issues=int(metrics.get("total_catalog_issues", 0)),
        eligible_catalog_issues=int(metrics.get("eligible_catalog_issues", 0)),
        asset_rows=int(metrics.get("asset_rows", metrics["total"])),
        issues_with_asset_row=int(metrics.get("issues_with_asset_row", 0)),
        queue_coverage_pct=float(metrics.get("queue_coverage_pct", 0)),
        eligible_without_asset_row=int(metrics.get("eligible_without_asset_row", 0)),
        eligible_with_url_not_queued=int(metrics.get("eligible_with_url_not_queued", 0)),
    )


@p104_cover_hydration_v1_router.post("/dry-run", response_model=P104CoverHydrationDryRunResponse)
def cover_hydration_dry_run(
    body: P104CoverHydrationDryRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> P104CoverHydrationDryRunResponse:
    del current_user
    _require_enabled()
    report = run_p104_dry_run(session, pilot_limit=body.pilot_limit, sync_limit=body.sync_limit)
    session.commit()
    return P104CoverHydrationDryRunResponse(report=report.to_dict())


@p104_cover_hydration_v1_router.post("/run", response_model=P104CoverHydrationRunResponse)
def cover_hydration_run(
    body: P104CoverHydrationRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> P104CoverHydrationRunResponse:
    del current_user
    _require_enabled()
    if body.confirm_write != "YES":
        raise HTTPException(status_code=400, detail="confirm_write must be YES")
    summary = run_p104_hydration(session, limit=body.limit, sync_limit=body.sync_limit, dry_run=False)
    return P104CoverHydrationRunResponse(summary=summary)
