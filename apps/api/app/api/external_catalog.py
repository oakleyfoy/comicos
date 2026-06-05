from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.external_catalog import (
    ExternalCatalogIssue,
    ExternalCatalogMatch,
    ExternalCatalogSyncRun,
)
from app.schemas.external_catalog import (
    ExternalCatalogCrosswalkRebuildRead,
    ExternalCatalogIssueListRead,
    ExternalCatalogIssueRead,
    ExternalCatalogSyncRunRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.external_catalog.crosswalk import MATCH_MISSING, rebuild_external_catalog_crosswalk
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME

external_catalog_v1_router = APIRouter(prefix="/api/v1", tags=["External Catalog API v1"])


def _issue_read(row: ExternalCatalogIssue) -> ExternalCatalogIssueRead:
    return ExternalCatalogIssueRead(
        id=int(row.id or 0),
        source_name=row.source_name,
        source_issue_id=row.source_issue_id,
        source_url=row.source_url,
        title=row.title,
        publisher=row.publisher,
        series_name=row.series_name,
        issue_number=row.issue_number,
        release_date=row.release_date,
        foc_date=row.foc_date,
        pull_count=row.pull_count,
        want_count=row.want_count,
        variant_count=row.variant_count,
        cover_image_url=row.cover_image_url,
        thumbnail_url=row.thumbnail_url,
        high_resolution_image_url=row.high_resolution_image_url,
        product_url=row.product_url,
        description=row.description,
        story_summary=row.story_summary,
        imprint=row.imprint,
        universe=row.universe,
        is_first_issue=row.is_first_issue,
        is_milestone_issue=row.is_milestone_issue,
        milestone_issue_number=row.milestone_issue_number,
        importance_signals_json=row.importance_signals_json,
        decision_signals_json=row.decision_signals_json,
        sync_status=row.sync_status,
        last_seen_at=row.last_seen_at,
    )


def attach_external_catalog_layer(app: FastAPI) -> None:
    app.include_router(external_catalog_v1_router)


@external_catalog_v1_router.get("/external-catalog/issues", response_model=ScanApiV1Envelope)
def list_external_catalog_issues(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source_name: str = Query(LOCG_SOURCE_NAME),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    del current_user
    rows = session.exec(
        select(ExternalCatalogIssue)
        .where(ExternalCatalogIssue.source_name == source_name)
        .order_by(ExternalCatalogIssue.release_date.desc().nulls_last(), ExternalCatalogIssue.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = len(
        session.exec(
            select(ExternalCatalogIssue).where(ExternalCatalogIssue.source_name == source_name)
        ).all()
    )
    items = [_issue_read(r) for r in rows]
    body = ExternalCatalogIssueListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=0)


@external_catalog_v1_router.get("/external-catalog/issues/{issue_id}", response_model=ScanApiV1Envelope)
def get_external_catalog_issue(
    issue_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    del current_user
    row = session.get(ExternalCatalogIssue, issue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="external issue not found")
    return wrap_object(_issue_read(row), owner_user_id=0)


@external_catalog_v1_router.get(
    "/external-catalog/issues/{issue_id}/decision-signals",
    response_model=ScanApiV1Envelope,
)
def get_external_catalog_decision_signals(
    issue_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    """RDE-oriented signal bundle for one external issue (ingest preview; does not run RDE)."""
    del current_user
    from app.models.external_catalog import ExternalCatalogCreator, ExternalCatalogVariant
    from app.services.external_catalog.decision_signals import build_decision_signals_for_issue_row

    row = session.get(ExternalCatalogIssue, issue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="external issue not found")
    if row.decision_signals_json:
        return wrap_object(row.decision_signals_json, owner_user_id=0)
    variants = session.exec(
        select(ExternalCatalogVariant).where(ExternalCatalogVariant.external_issue_id == issue_id)
    ).all()
    creators = session.exec(
        select(ExternalCatalogCreator).where(ExternalCatalogCreator.external_issue_id == issue_id)
    ).all()
    payload = build_decision_signals_for_issue_row(row, variants=variants, creators=creators)
    return wrap_object(payload, owner_user_id=0)


@external_catalog_v1_router.get("/external-catalog/missing-from-lunar", response_model=ScanApiV1Envelope)
def list_missing_from_lunar(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    rows = session.exec(
        select(ExternalCatalogIssue, ExternalCatalogMatch)
        .join(ExternalCatalogMatch, ExternalCatalogMatch.external_issue_id == ExternalCatalogIssue.id)
        .where(
            ExternalCatalogMatch.owner_user_id == owner_user_id,
            ExternalCatalogMatch.match_status == MATCH_MISSING,
        )
        .order_by(ExternalCatalogIssue.pull_count.desc().nulls_last(), ExternalCatalogIssue.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    items = [_issue_read(issue) for issue, _match in rows]
    total = len(items)
    body = ExternalCatalogIssueListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@external_catalog_v1_router.get("/external-catalog/sync-runs", response_model=ScanApiV1Envelope)
def list_external_catalog_sync_runs(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    del current_user
    rows = session.exec(
        select(ExternalCatalogSyncRun)
        .order_by(ExternalCatalogSyncRun.started_at.desc(), ExternalCatalogSyncRun.id.desc())
        .limit(limit)
    ).all()
    items = [
        ExternalCatalogSyncRunRead(
            id=int(r.id or 0),
            source_name=r.source_name,
            sync_type=r.sync_type,
            status=r.status,
            pages_scanned=r.pages_scanned,
            issues_created=r.issues_created,
            issues_updated=r.issues_updated,
            errors_count=r.errors_count,
            started_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in rows
    ]
    return wrap_standard_list(items, owner_user_id=0)


@external_catalog_v1_router.post("/external-catalog/crosswalk/rebuild", response_model=ScanApiV1Envelope)
def rebuild_crosswalk_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    summary = rebuild_external_catalog_crosswalk(session, owner_user_id=int(current_user.id))
    body = ExternalCatalogCrosswalkRebuildRead(**summary)
    return wrap_object(body, owner_user_id=int(current_user.id))
