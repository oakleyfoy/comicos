from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.exit_candidate import ExitCandidateListRead, ExitCandidateSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.exit_candidates import (
    build_exit_candidate_summary,
    list_exit_candidates,
    refresh_and_list_latest_exit_candidates,
)

exit_candidate_v1_router = APIRouter(prefix="/api/v1", tags=["Exit Candidates API v1 (P56-01)"])


def attach_exit_candidate_layer(app: FastAPI) -> None:
    app.include_router(exit_candidate_v1_router)


@exit_candidate_v1_router.get("/exit-candidates", response_model=ScanApiV1Envelope)
def v1_list_exit_candidates(
    candidate_reason: str | None = None,
    score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_exit_candidates(
        session,
        owner_user_id=int(current_user.id),
        candidate_reason=candidate_reason,
        score_min=score_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = ExitCandidateListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@exit_candidate_v1_router.get("/exit-candidates/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_exit_candidates(
    candidate_reason: str | None = None,
    score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_exit_candidates(
        session,
        owner_user_id=int(current_user.id),
        candidate_reason=candidate_reason,
        score_min=score_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = ExitCandidateListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@exit_candidate_v1_router.get("/exit-candidates/summary", response_model=ScanApiV1Envelope)
def v1_exit_candidate_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_exit_candidate_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
