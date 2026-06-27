"""P103.5 GCD identity + UPC backfill dashboard API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.p1035_gcd_identity_dashboard import (
    GcdIdentityBackfillDryRunRequest,
    GcdIdentityBackfillJobListResponse,
    GcdIdentityBackfillJobModel,
    GcdIdentityBackfillJobResponse,
    GcdIdentityBackfillStatusResponse,
    GcdIdentityBackfillWriteRequest,
)
from app.services.gcd_catalog_import_dashboard_service import ensure_catalog_cache, resolve_cache_path, resolve_gcd_path
from app.services.p103_gcd_catalog_enrichment_service import validate_enrichment_filters
from app.services.p1035_gcd_identity_dashboard_service import (
    list_p1035_identity_jobs,
    load_p1035_identity_job,
    p1035_status_dict,
    rollback_p1035_identity_job,
    run_p1035_dry_run_job,
    run_p1035_write_job,
)

gcd_identity_backfill_v1_router = APIRouter(
    prefix="/api/v1/catalog-enrichment",
    tags=["Catalog Enrichment"],
)


def attach_gcd_identity_backfill_dashboard_layer(app) -> None:
    app.include_router(gcd_identity_backfill_v1_router)


def _require_enabled() -> None:
    if not get_settings().gcd_enrichment_enabled:
        raise HTTPException(status_code=503, detail="GCD enrichment is disabled")


@gcd_identity_backfill_v1_router.get(
    "/gcd-identity-backfill/status",
    response_model=GcdIdentityBackfillStatusResponse,
)
def gcd_identity_backfill_status(
    current_user: User = Depends(get_current_user),
) -> GcdIdentityBackfillStatusResponse:
    del current_user
    _require_enabled()
    return GcdIdentityBackfillStatusResponse(**p1035_status_dict())


@gcd_identity_backfill_v1_router.post(
    "/gcd-identity-backfill/dry-run",
    response_model=GcdIdentityBackfillJobResponse,
)
def gcd_identity_backfill_dry_run(
    body: GcdIdentityBackfillDryRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdIdentityBackfillJobResponse:
    del current_user
    _require_enabled()
    gcd_path = resolve_gcd_path()
    if not gcd_path.exists():
        raise HTTPException(status_code=404, detail=f"GCD database not found: {gcd_path}")
    cache_path = resolve_cache_path()
    ensure_catalog_cache(session, cache_path, refresh=body.refresh_cache)
    filters = validate_enrichment_filters(
        write_batch=False,
        limit=body.limit,
        publisher=body.publisher,
        year=body.year,
        year_from=body.year_from,
        year_to=body.year_to,
        confirm_write=None,
        all_catalog=body.all_catalog,
    )
    if filters is None:
        raise HTTPException(status_code=400, detail="Invalid dry-run filters")
    job = run_p1035_dry_run_job(
        session,
        gcd_path=gcd_path,
        cache_path=cache_path,
        filters=filters,
        benchmark=body.benchmark,
        resume_job_id=body.resume_job_id,
    )
    return GcdIdentityBackfillJobResponse(
        job=GcdIdentityBackfillJobModel(**load_p1035_identity_job(session, int(job.id or 0)))
    )


@gcd_identity_backfill_v1_router.post(
    "/gcd-identity-backfill/write-batch",
    response_model=GcdIdentityBackfillJobResponse,
)
def gcd_identity_backfill_write_batch(
    body: GcdIdentityBackfillWriteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdIdentityBackfillJobResponse:
    del current_user
    _require_enabled()
    if body.confirm_write != "YES":
        raise HTTPException(status_code=400, detail="confirm_write must be YES")
    gcd_path = resolve_gcd_path()
    if not gcd_path.exists():
        raise HTTPException(status_code=404, detail=f"GCD database not found: {gcd_path}")
    cache_path = resolve_cache_path()
    ensure_catalog_cache(session, cache_path, refresh=body.refresh_cache)
    filters = validate_enrichment_filters(
        write_batch=True,
        limit=body.limit,
        publisher=body.publisher,
        year=body.year,
        year_from=body.year_from,
        year_to=body.year_to,
        confirm_write=body.confirm_write,
        all_catalog=body.all_catalog,
    )
    if filters is None:
        raise HTTPException(status_code=400, detail="Invalid write filters")
    job = run_p1035_write_job(
        session,
        gcd_path=gcd_path,
        cache_path=cache_path,
        filters=filters,
        confirm_write=body.confirm_write,
        resume_job_id=body.resume_job_id,
    )
    return GcdIdentityBackfillJobResponse(
        job=GcdIdentityBackfillJobModel(**load_p1035_identity_job(session, int(job.id or 0)))
    )


@gcd_identity_backfill_v1_router.get(
    "/gcd-identity-backfill/jobs",
    response_model=GcdIdentityBackfillJobListResponse,
)
def gcd_identity_backfill_jobs(
    limit: int = 30,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdIdentityBackfillJobListResponse:
    del current_user
    _require_enabled()
    jobs = list_p1035_identity_jobs(session, limit=limit)
    return GcdIdentityBackfillJobListResponse(jobs=[GcdIdentityBackfillJobModel(**j) for j in jobs])


@gcd_identity_backfill_v1_router.post("/gcd-identity-backfill/jobs/{job_id}/rollback")
def gcd_identity_backfill_rollback(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    del current_user
    _require_enabled()
    try:
        return rollback_p1035_identity_job(session, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
