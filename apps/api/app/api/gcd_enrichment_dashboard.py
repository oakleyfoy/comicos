"""P103 GCD catalog enrichment dashboard API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.p103_gcd_enrichment_dashboard import (
    GcdEnrichmentDryRunRequest,
    GcdEnrichmentJobListResponse,
    GcdEnrichmentJobModel,
    GcdEnrichmentJobResponse,
    GcdEnrichmentStatusResponse,
    GcdEnrichmentWriteRequest,
)
from app.services.gcd_catalog_import_dashboard_service import ensure_catalog_cache, resolve_cache_path, resolve_gcd_path
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters, validate_enrichment_filters
from app.services.p103_gcd_enrichment_dashboard_service import (
    list_p103_enrichment_jobs,
    load_p103_enrichment_job,
    p103_status_dict,
    run_p103_dry_run_job,
    run_p103_write_batch_job,
)
from app.services.p103_gcd_enrichment_rollback_service import rollback_p103_enrichment_job

gcd_enrichment_v1_router = APIRouter(prefix="/api/v1/catalog-enrichment", tags=["Catalog Enrichment"])


def attach_gcd_enrichment_dashboard_layer(app) -> None:
    app.include_router(gcd_enrichment_v1_router)


def _require_enabled() -> None:
    if not get_settings().gcd_enrichment_enabled:
        raise HTTPException(status_code=503, detail="GCD enrichment is disabled")


@gcd_enrichment_v1_router.get("/gcd/status", response_model=GcdEnrichmentStatusResponse)
def gcd_enrichment_status(
    current_user: User = Depends(get_current_user),
) -> GcdEnrichmentStatusResponse:
    del current_user
    _require_enabled()
    return GcdEnrichmentStatusResponse(**p103_status_dict())


@gcd_enrichment_v1_router.post("/gcd/dry-run", response_model=GcdEnrichmentJobResponse)
def gcd_enrichment_dry_run(
    body: GcdEnrichmentDryRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdEnrichmentJobResponse:
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
    )
    if filters is None:
        raise HTTPException(status_code=400, detail="Invalid dry-run filters")
    job = run_p103_dry_run_job(session, gcd_path=gcd_path, cache_path=cache_path, filters=filters)
    return GcdEnrichmentJobResponse(job=GcdEnrichmentJobModel(**load_p103_enrichment_job(session, int(job.id or 0))))


@gcd_enrichment_v1_router.post("/gcd/write-batch", response_model=GcdEnrichmentJobResponse)
def gcd_enrichment_write_batch(
    body: GcdEnrichmentWriteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdEnrichmentJobResponse:
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
    )
    if filters is None:
        raise HTTPException(status_code=400, detail="Invalid write filters")
    job = run_p103_write_batch_job(
        session,
        gcd_path=gcd_path,
        cache_path=cache_path,
        filters=filters,
        confirm_write=body.confirm_write,
    )
    return GcdEnrichmentJobResponse(job=GcdEnrichmentJobModel(**load_p103_enrichment_job(session, int(job.id or 0))))


@gcd_enrichment_v1_router.get("/jobs", response_model=GcdEnrichmentJobListResponse)
def gcd_enrichment_jobs(
    limit: int = 30,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdEnrichmentJobListResponse:
    del current_user
    _require_enabled()
    jobs = list_p103_enrichment_jobs(session, limit=limit)
    return GcdEnrichmentJobListResponse(jobs=[GcdEnrichmentJobModel(**j) for j in jobs])


@gcd_enrichment_v1_router.get("/jobs/{job_id}", response_model=GcdEnrichmentJobResponse)
def gcd_enrichment_job_detail(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdEnrichmentJobResponse:
    del current_user
    _require_enabled()
    try:
        job = load_p103_enrichment_job(session, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GcdEnrichmentJobResponse(job=GcdEnrichmentJobModel(**job))


@gcd_enrichment_v1_router.post("/jobs/{job_id}/rollback")
def gcd_enrichment_rollback(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    del current_user
    _require_enabled()
    try:
        return rollback_p103_enrichment_job(session, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
