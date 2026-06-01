from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.next_issue import NextIssueListRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_standard_list
from app.services.next_issues import list_next_issues, refresh_and_list_latest_next_issues

next_issue_v1_router = APIRouter(prefix="/api/v1", tags=["Next Issues API v1 (P58-02)"])


def attach_next_issue_layer(app: FastAPI) -> None:
    app.include_router(next_issue_v1_router)


@next_issue_v1_router.get("/next-issues", response_model=ScanApiV1Envelope)
def v1_list_next_issues(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_next_issues(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = NextIssueListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@next_issue_v1_router.get("/next-issues/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_next_issues(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_next_issues(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = NextIssueListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
