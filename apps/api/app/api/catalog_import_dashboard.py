"""GCD catalog import dashboard API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.catalog_import_dashboard import (
    GcdImportCellStatsModel,
    GcdImportDryRunRequest,
    GcdImportJobListResponse,
    GcdImportJobModel,
    GcdImportJobResponse,
    GcdImportMatrixRequest,
    GcdImportMatrixResponse,
    GcdImportScopeResponse,
    GcdImportStatusResponse,
    GcdImportWriteRequest,
)
from app.services.gcd_catalog_import_dashboard_service import (
    analyze_gcd_scope,
    build_gcd_import_matrix,
    ensure_catalog_cache,
    load_job_dashboard_dict,
    job_to_dashboard_dict,
    list_gcd_import_jobs,
    preview_rows_to_csv,
    resolve_cache_path,
    resolve_gcd_path,
    run_gcd_write_batch_job,
    run_matrix_job,
    run_scope_dry_run_job,
)
from app.services.gcd_catalog_import_rollback_service import rollback_gcd_import_job
from app.services.p101_catalog_cache_service import YEAR_MAX, YEAR_MIN
from app.services.p102_gcd_modern_acquisition_service import FOCUS_PUBLISHERS
from app.services.p102_gcd_modern_acquisition_write_service import MAX_WRITE_BATCH_LIMIT, WriteBatchFilters

catalog_import_v1_router = APIRouter(prefix="/api/v1/catalog-import", tags=["Catalog Import"])


def attach_catalog_import_dashboard_layer(app) -> None:
    app.include_router(catalog_import_v1_router)


def _require_gcd_enabled() -> None:
    if not get_settings().gcd_import_enabled:
        raise HTTPException(status_code=503, detail="GCD import is disabled")


@catalog_import_v1_router.get("/gcd/status", response_model=GcdImportStatusResponse)
def gcd_import_status(
    current_user: User = Depends(get_current_user),
) -> GcdImportStatusResponse:
    del current_user
    _require_gcd_enabled()
    gcd_path = resolve_gcd_path()
    cache_path = resolve_cache_path()
    settings = get_settings()
    return GcdImportStatusResponse(
        gcd_database=str(gcd_path),
        gcd_database_exists=gcd_path.exists(),
        catalog_cache=str(cache_path),
        catalog_cache_exists=cache_path.exists(),
        gcd_import_enabled=settings.gcd_import_enabled,
        max_write_batch_limit=MAX_WRITE_BATCH_LIMIT,
        focus_publishers=list(FOCUS_PUBLISHERS),
        default_year_from=YEAR_MIN,
        default_year_to=YEAR_MAX,
    )


@catalog_import_v1_router.post("/gcd/matrix", response_model=GcdImportMatrixResponse)
def gcd_import_matrix(
    body: GcdImportMatrixRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdImportMatrixResponse:
    del current_user
    _require_gcd_enabled()
    gcd_path = resolve_gcd_path()
    if not gcd_path.exists():
        raise HTTPException(status_code=404, detail=f"GCD database not found: {gcd_path}")
    cache_path = resolve_cache_path()
    ensure_catalog_cache(session, cache_path, refresh=body.refresh_cache)
    job = run_matrix_job(
        session,
        gcd_path=gcd_path,
        cache_path=cache_path,
        year_from=body.year_from,
        year_to=body.year_to,
    )
    report = dict((job.config or {}).get("report") or {})
    return GcdImportMatrixResponse(
        generated_at=str(report.get("generated_at") or ""),
        year_from=body.year_from,
        year_to=body.year_to,
        elapsed_seconds=float(report.get("elapsed_seconds") or 0),
        job_id=int(job.id or 0),
        cells=report.get("cells") or [],
    )


@catalog_import_v1_router.get("/gcd/scope", response_model=GcdImportScopeResponse)
def gcd_import_scope(
    publisher: str = Query(...),
    year: int = Query(..., ge=1900, le=2100),
    preview_limit: int = Query(default=100, ge=1, le=500),
    refresh_cache: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdImportScopeResponse:
    del current_user
    _require_gcd_enabled()
    if publisher not in FOCUS_PUBLISHERS:
        raise HTTPException(status_code=400, detail=f"Unsupported publisher: {publisher}")
    gcd_path = resolve_gcd_path()
    if not gcd_path.exists():
        raise HTTPException(status_code=404, detail=f"GCD database not found: {gcd_path}")
    cache_path = resolve_cache_path()
    ensure_catalog_cache(session, cache_path, refresh=refresh_cache)
    analysis = analyze_gcd_scope(
        gcd_path=gcd_path,
        cache_path=cache_path,
        publisher=publisher,
        year=year,
        preview_limit=preview_limit,
    )
    return GcdImportScopeResponse(
        publisher=publisher,
        year=year,
        elapsed_seconds=float(analysis.get("elapsed_seconds") or 0),
        stats=GcdImportCellStatsModel.model_validate(analysis.get("stats") or {}),
        preview_rows=analysis.get("preview_rows") or [],
    )


@catalog_import_v1_router.get("/gcd/scope.csv", response_class=PlainTextResponse)
def gcd_import_scope_csv(
    publisher: str = Query(...),
    year: int = Query(..., ge=1900, le=2100),
    preview_limit: int = Query(default=100, ge=1, le=500),
    refresh_cache: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PlainTextResponse:
    del current_user
    _require_gcd_enabled()
    if publisher not in FOCUS_PUBLISHERS:
        raise HTTPException(status_code=400, detail=f"Unsupported publisher: {publisher}")
    gcd_path = resolve_gcd_path()
    cache_path = resolve_cache_path()
    ensure_catalog_cache(session, cache_path, refresh=refresh_cache)
    analysis = analyze_gcd_scope(
        gcd_path=gcd_path,
        cache_path=cache_path,
        publisher=publisher,
        year=year,
        preview_limit=preview_limit,
    )
    csv_text = preview_rows_to_csv(analysis.get("preview_rows") or [])
    filename = f"gcd_preview_{publisher}_{year}.csv"
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@catalog_import_v1_router.post("/gcd/dry-run", response_model=GcdImportJobResponse)
def gcd_import_dry_run(
    body: GcdImportDryRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdImportJobResponse:
    del current_user
    _require_gcd_enabled()
    if body.publisher not in FOCUS_PUBLISHERS:
        raise HTTPException(status_code=400, detail=f"Unsupported publisher: {body.publisher}")
    gcd_path = resolve_gcd_path()
    if not gcd_path.exists():
        raise HTTPException(status_code=404, detail=f"GCD database not found: {gcd_path}")
    cache_path = resolve_cache_path()
    ensure_catalog_cache(session, cache_path, refresh=body.refresh_cache)
    job = run_scope_dry_run_job(
        session,
        gcd_path=gcd_path,
        cache_path=cache_path,
        publisher=body.publisher,
        year=body.year,
        preview_limit=body.preview_limit,
    )
    return GcdImportJobResponse(job=GcdImportJobModel(**load_job_dashboard_dict(session, int(job.id or 0))))


@catalog_import_v1_router.post("/gcd/write-batch", response_model=GcdImportJobResponse)
def gcd_import_write_batch(
    body: GcdImportWriteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdImportJobResponse:
    del current_user
    _require_gcd_enabled()
    if body.publisher not in FOCUS_PUBLISHERS:
        raise HTTPException(status_code=400, detail=f"Unsupported publisher: {body.publisher}")
    if body.confirm_write != "YES":
        raise HTTPException(status_code=400, detail='confirm_write must be "YES"')
    gcd_path = resolve_gcd_path()
    if not gcd_path.exists():
        raise HTTPException(status_code=404, detail=f"GCD database not found: {gcd_path}")
    cache_path = resolve_cache_path()
    ensure_catalog_cache(session, cache_path, refresh=body.refresh_cache)
    filters = WriteBatchFilters(
        publisher=body.publisher,
        year_from=body.year,
        year_to=body.year,
        limit=body.limit,
    )
    try:
        job = run_gcd_write_batch_job(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            confirm_write=body.confirm_write,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GcdImportJobResponse(job=GcdImportJobModel(**load_job_dashboard_dict(session, int(job.id or 0))))


@catalog_import_v1_router.get("/jobs", response_model=GcdImportJobListResponse)
def list_import_jobs(
    limit: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdImportJobListResponse:
    del current_user
    jobs = list_gcd_import_jobs(session, limit=limit)
    return GcdImportJobListResponse(jobs=[GcdImportJobModel(**j) for j in jobs])


@catalog_import_v1_router.get("/jobs/{job_id}", response_model=GcdImportJobResponse)
def get_import_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GcdImportJobResponse:
    del current_user
    from app.models.catalog_p97 import CatalogImportJob

    job = session.get(CatalogImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return GcdImportJobResponse(job=GcdImportJobModel(**load_job_dashboard_dict(session, int(job.id or 0))))


@catalog_import_v1_router.post("/jobs/{job_id}/rollback")
def rollback_import_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    del current_user
    _require_gcd_enabled()
    try:
        return rollback_gcd_import_job(session, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
