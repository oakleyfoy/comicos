from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.p89_sell_candidate import P89SellCandidate
from app.schemas.p89_sell_candidate import (
    P89SellCandidateGenerateResponse,
    P89SellCandidateListRead,
    P89SellCandidateSummaryRead,
)
from app.schemas.sell_candidate import (
    SellCandidateRecommendationListRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.sell_candidate_service import (
    build_p89_sell_candidate_summary,
    list_p89_sell_candidates,
    recalculate_sell_candidates,
    _to_read,
)
from app.services.sell_candidates import (
    get_sell_candidate_recommendation,
    list_latest_sell_candidate_recommendations,
)

sell_candidate_v1_router = APIRouter(prefix="/api/v1", tags=["Sell Candidates API v1 (P89-01)"])


def attach_sell_candidate_layer(app: FastAPI) -> None:
    app.include_router(sell_candidate_v1_router)


@sell_candidate_v1_router.get("/sell-candidates", response_model=ScanApiV1Envelope)
def v1_list_sell_candidates(
    recommendation: str | None = None,
    confidence: str | None = Query(default=None, description="HIGH, MEDIUM, or LOW"),
    minimum_score: float | None = Query(default=None, ge=0.0, le=100.0),
    sort: str = Query(default="sell_score"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_p89_sell_candidates(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        confidence=confidence,
        minimum_score=minimum_score,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    body = P89SellCandidateListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@sell_candidate_v1_router.get("/sell-candidates/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_sell_candidates(
    recommendation: str | None = None,
    publisher: str | None = None,
    confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_latest_sell_candidate_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        publisher=publisher,
        min_confidence=confidence,
        limit=limit,
        offset=offset,
    )
    body = SellCandidateRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@sell_candidate_v1_router.get("/sell-candidates/summary", response_model=ScanApiV1Envelope)
def v1_sell_candidate_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_p89_sell_candidate_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@sell_candidate_v1_router.post("/sell-candidates/generate", response_model=ScanApiV1Envelope)
def v1_generate_sell_candidates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    summary = recalculate_sell_candidates(session, owner_user_id=int(current_user.id), dry_run=False)
    session.commit()
    body = P89SellCandidateGenerateResponse(
        created_count=int(summary.get("created") or 0),
        updated_count=int(summary.get("updated") or 0),
        candidates=int(summary.get("candidates") or 0),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@sell_candidate_v1_router.get("/sell-candidates/{recommendation_id}", response_model=ScanApiV1Envelope)
def v1_get_sell_candidate(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = session.get(P89SellCandidate, recommendation_id)
    if row is None or row.owner_user_id != int(current_user.id) or row.status != "ACTIVE":
        try:
            body = get_sell_candidate_recommendation(
                session,
                owner_user_id=int(current_user.id),
                recommendation_id=recommendation_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return wrap_object(body, owner_user_id=int(current_user.id))
    return wrap_object(_to_read(session, row=row), owner_user_id=int(current_user.id))
