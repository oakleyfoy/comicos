from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_acquisition import (
    MarketplaceAcquisitionCandidateCreate,
    MarketplaceAcquisitionCandidateUpdate,
    MarketplaceAcquisitionListRead,
    MarketplaceAcquisitionSummaryRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_acquisitions import (
    MarketplaceCandidateNotFoundError,
    build_marketplace_acquisition_summary,
    create_marketplace_candidate,
    evaluate_marketplace_candidate,
    get_marketplace_candidate,
    list_marketplace_candidates,
    update_marketplace_candidate,
)

marketplace_acquisition_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Acquisitions API v1 (P55-04)"])


def attach_marketplace_acquisition_layer(app: FastAPI) -> None:
    app.include_router(marketplace_acquisition_v1_router)


@marketplace_acquisition_v1_router.get("/marketplace-acquisitions/summary", response_model=ScanApiV1Envelope)
def v1_marketplace_acquisition_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_marketplace_acquisition_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_acquisition_v1_router.get("/marketplace-acquisitions", response_model=ScanApiV1Envelope)
def v1_list_marketplace_acquisitions(
    recommendation: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_marketplace_candidates(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        status=status,
        source_type=source_type,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = MarketplaceAcquisitionListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_acquisition_v1_router.post("/marketplace-acquisitions", response_model=ScanApiV1Envelope)
def v1_create_marketplace_acquisition(
    payload: MarketplaceAcquisitionCandidateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_marketplace_candidate(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_acquisition_v1_router.get("/marketplace-acquisitions/{candidate_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_acquisition(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_marketplace_candidate(session, owner_user_id=int(current_user.id), candidate_id=candidate_id)
    except MarketplaceCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_acquisition_v1_router.patch("/marketplace-acquisitions/{candidate_id}", response_model=ScanApiV1Envelope)
def v1_patch_marketplace_acquisition(
    candidate_id: int,
    payload: MarketplaceAcquisitionCandidateUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = update_marketplace_candidate(
            session,
            owner_user_id=int(current_user.id),
            candidate_id=candidate_id,
            payload=payload,
        )
    except MarketplaceCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_acquisition_v1_router.post("/marketplace-acquisitions/{candidate_id}/evaluate", response_model=ScanApiV1Envelope)
def v1_evaluate_marketplace_acquisition(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = evaluate_marketplace_candidate(
            session,
            owner_user_id=int(current_user.id),
            candidate_id=candidate_id,
        )
    except MarketplaceCandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))
