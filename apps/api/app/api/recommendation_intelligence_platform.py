"""P62 Recommendation Intelligence Platform API (V3 preview + buy queue)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.buy_queue_intelligence import (
    BuyQueueBuildResultRead,
    BuyQueueCertificationRead,
    BuyQueueItemRead,
    BuyQueueItemStatusUpdate,
    BuyQueueListRead,
    BuyQueueSnapshotRead,
)
from app.schemas.recommendation_intelligence_v3 import (
    V3CertificationRead,
    V3PreviewItemRead,
    V3PreviewRead,
    V3ReadinessRead,
    V3ScoreComponentRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.p62_feature_flags import p62_v3_preview_enabled
from app.services.recommendation_v3_certification import certify_recommendation_v3_preview
from app.services.buy_queue_certification import certify_buy_queue
from app.services.buy_queue_service import (
    build_buy_queue,
    get_latest_buy_queue_snapshot,
    list_buy_queue_items,
    update_buy_queue_item_status,
)
from app.services.recommendation_v3_preview_service import build_recommendation_v3_preview

recommendation_intelligence_v1_router = APIRouter(
    prefix="/api/v1/recommendation-intelligence",
    tags=["P62 Recommendation Intelligence"],
)


def attach_recommendation_intelligence_platform_layer(app: FastAPI) -> None:
    app.include_router(recommendation_intelligence_v1_router)


def _preview_read(raw: dict) -> V3PreviewRead:
    readiness_raw = raw.get("readiness")
    readiness = None
    if isinstance(readiness_raw, dict):
        readiness = V3ReadinessRead(**readiness_raw)
    items = [
        V3PreviewItemRead(
            title=str(row["title"]),
            recommendation_type=str(row["recommendation_type"]),
            v2_priority_score=float(row["v2_priority_score"]),
            v2_confidence_score=float(row["v2_confidence_score"]),
            v3_preview_score=float(row["v3_preview_score"]),
            release_issue_id=row.get("release_issue_id"),
            demand_intel_status=str(row["demand_intel_status"]),
            components=[V3ScoreComponentRead(**c) for c in row.get("components") or []],
        )
        for row in raw.get("items") or []
    ]
    return V3PreviewRead(
        enabled=bool(raw.get("enabled")),
        not_ready=bool(raw.get("not_ready")),
        reason_codes=list(raw.get("reason_codes") or []),
        items=items,
        readiness=readiness,
        persisted_row_count=int(raw.get("persisted_row_count") or 0),
        v2_mutated=bool(raw.get("v2_mutated")),
        preview_count=int(raw.get("preview_count") or len(items)),
    )


@recommendation_intelligence_v1_router.get("/v3/preview", response_model=ScanApiV1Envelope)
def v1_recommendation_v3_preview(
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if not p62_v3_preview_enabled():
        raise HTTPException(status_code=403, detail="P62_V3_PREVIEW_DISABLED")
    raw = build_recommendation_v3_preview(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
    )
    return wrap_object(_preview_read(raw), owner_user_id=int(current_user.id))


@recommendation_intelligence_v1_router.get("/v3/certification", response_model=ScanApiV1Envelope)
def v1_recommendation_v3_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    cert = certify_recommendation_v3_preview(session, owner_user_id=int(current_user.id))
    body = V3CertificationRead(**cert)
    return wrap_object(body, owner_user_id=int(current_user.id))


def _snapshot_read(row) -> BuyQueueSnapshotRead:
    return BuyQueueSnapshotRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        snapshot_date=row.snapshot_date,
        generated_at=row.generated_at,
        total_items=row.total_items,
        metadata_json=row.metadata_json or {},
    )


def _item_read(row) -> BuyQueueItemRead:
    return BuyQueueItemRead(
        id=int(row.id or 0),
        snapshot_id=int(row.snapshot_id),
        owner_id=int(row.owner_user_id),
        recommendation_id=row.recommendation_id,
        release_issue_id=row.release_issue_id,
        external_catalog_issue_id=row.external_catalog_issue_id,
        title=row.title,
        issue_number=row.issue_number,
        publisher=row.publisher,
        priority_score=row.priority_score,
        recommendation_score=row.recommendation_score,
        demand_score=row.demand_score,
        velocity_score=row.velocity_score,
        spec_score=row.spec_score,
        buy_reason=row.buy_reason,
        quantity_recommended=row.quantity_recommended,
        estimated_cost=row.estimated_cost,
        foc_date=row.foc_date,
        release_date=row.release_date,
        status=row.status,
    )


def _buy_queue_list(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
) -> BuyQueueListRead:
    snap = get_latest_buy_queue_snapshot(session, owner_user_id=owner_user_id)
    if snap is None or snap.id is None:
        return BuyQueueListRead(snapshot=None, items=[], total_items=0, limit=limit, offset=offset)
    items, total = list_buy_queue_items(session, snapshot_id=int(snap.id), limit=limit, offset=offset)
    return BuyQueueListRead(
        snapshot=_snapshot_read(snap),
        items=[_item_read(i) for i in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )


@recommendation_intelligence_v1_router.get("/buy-queue", response_model=ScanApiV1Envelope)
def v1_buy_queue(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = _buy_queue_list(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_intelligence_v1_router.get("/buy-queue/latest", response_model=ScanApiV1Envelope)
def v1_buy_queue_latest(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = _buy_queue_list(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_intelligence_v1_router.post("/buy-queue/build", response_model=ScanApiV1Envelope)
def v1_buy_queue_build(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    snap = build_buy_queue(session, owner_user_id=int(current_user.id))
    body = BuyQueueBuildResultRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items)
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_intelligence_v1_router.patch("/buy-queue/item/{item_id}", response_model=ScanApiV1Envelope)
def v1_buy_queue_item_patch(
    item_id: int,
    payload: BuyQueueItemStatusUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        item = update_buy_queue_item_status(
            session,
            item_id=item_id,
            owner_user_id=int(current_user.id),
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(_item_read(item), owner_user_id=int(current_user.id))


@recommendation_intelligence_v1_router.get("/buy-queue/certification", response_model=ScanApiV1Envelope)
def v1_buy_queue_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    cert = certify_buy_queue(session, owner_user_id=int(current_user.id))
    return wrap_object(BuyQueueCertificationRead(**cert), owner_user_id=int(current_user.id))
