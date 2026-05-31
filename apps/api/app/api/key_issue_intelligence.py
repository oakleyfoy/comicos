from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.key_issue_intelligence import KeyIssueDashboardRead, KeyIssueListResponse, KeyIssueRefreshResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.key_issue_dashboard import build_key_issue_dashboard, list_key_issues_for_owner
from app.services.key_issue_refresh import refresh_owner_key_issues

key_issue_intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Key Issue Intelligence API v1 (P51-02)"])


def attach_key_issue_intelligence_layer(app: FastAPI) -> None:
    app.include_router(key_issue_intelligence_v1_router)


def _list_by_route(
    session: Session,
    *,
    owner_user_id: int,
    key_issue_type: str,
    limit: int,
    offset: int,
) -> KeyIssueListResponse:
    items, total = list_key_issues_for_owner(session, owner_user_id=owner_user_id, limit=500, offset=0)
    filtered = [row for row in items if row.key_issue_type == key_issue_type]
    page = filtered[offset : offset + limit]
    return KeyIssueListResponse(items=page, total_items=len(filtered), limit=limit, offset=offset)


@key_issue_intelligence_v1_router.get("/key-issues", response_model=ScanApiV1Envelope)
def v1_key_issues(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    items, total = list_key_issues_for_owner(session, owner_user_id=int(current_user.id), limit=lim, offset=off)
    body = KeyIssueListResponse(items=items, total_items=total, limit=lim, offset=off)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@key_issue_intelligence_v1_router.get("/key-issues/top", response_model=ScanApiV1Envelope)
def v1_key_issues_top(
    limit: int = 25,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 100))
    dashboard = build_key_issue_dashboard(session, owner_user_id=int(current_user.id), limit=lim)
    body = KeyIssueListResponse(items=dashboard.top_key_issues, total_items=len(dashboard.top_key_issues), limit=lim, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@key_issue_intelligence_v1_router.get("/key-issues/milestones", response_model=ScanApiV1Envelope)
def v1_key_issues_milestones(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = _list_by_route(
        session,
        owner_user_id=int(current_user.id),
        key_issue_type="MILESTONE_NUMBERING",
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@key_issue_intelligence_v1_router.get("/key-issues/anniversaries", response_model=ScanApiV1Envelope)
def v1_key_issues_anniversaries(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = _list_by_route(
        session,
        owner_user_id=int(current_user.id),
        key_issue_type="ANNIVERSARY",
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@key_issue_intelligence_v1_router.get("/key-issues/first-appearances", response_model=ScanApiV1Envelope)
def v1_key_issues_first_appearances(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = _list_by_route(
        session,
        owner_user_id=int(current_user.id),
        key_issue_type="FIRST_APPEARANCE",
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@key_issue_intelligence_v1_router.get("/key-issues/dashboard", response_model=ScanApiV1Envelope)
def v1_key_issues_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: KeyIssueDashboardRead = build_key_issue_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@key_issue_intelligence_v1_router.post("/key-issues/refresh", response_model=ScanApiV1Envelope)
def v1_key_issues_refresh(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: KeyIssueRefreshResponse = refresh_owner_key_issues(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
