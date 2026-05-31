from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.release_watchlist import (
    AutoWatchlistsRunResponse,
    CollectionContinuityAlertListResponse,
    CollectionRunListResponse,
    DeleteWatchlistItemResponse,
    ReleaseReminderListResponse,
    ReleaseWatchlistCreateRequest,
    ReleaseWatchlistItemCreateRequest,
    ReleaseWatchlistListResponse,
    WatchlistAlertsRunResponse,
    WatchlistAgentExecutionListResponse,
    WatchlistAgentExecutionRead,
    WatchlistRemindersRunResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.auto_watchlist_agent import run_auto_watchlists
from app.services.continuity_dashboard import build_continuity_dashboard
from app.services.foc_reminder_agent import run_foc_reminders
from app.services.release_reminder_agent import list_reminders_for_owner, run_release_reminders
from app.services.release_watchlist_execution import list_executions_for_owner
from app.services.release_watchlists import add_watchlist_item, create_watchlist, list_watchlists, remove_watchlist_item
from app.services.run_continuity_agent import list_alerts_for_owner, list_runs_for_owner, run_continuity_detection

release_watchlists_v1_router = APIRouter(prefix="/api/v1", tags=["Release Watchlists API v1 (P50-02)"])


def attach_release_watchlists_layer(app: FastAPI) -> None:
    app.include_router(release_watchlists_v1_router)


@release_watchlists_v1_router.get("/release-watchlists/runs", response_model=ScanApiV1Envelope)
def v1_release_runs(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_runs_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = CollectionRunListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.get("/release-watchlists/alerts", response_model=ScanApiV1Envelope)
def v1_release_alerts(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_alerts_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = CollectionContinuityAlertListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.get("/release-watchlists/reminders", response_model=ScanApiV1Envelope)
def v1_release_reminders(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_reminders_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReleaseReminderListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.get("/release-watchlists/watchlists", response_model=ScanApiV1Envelope)
def v1_release_watchlists(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_watchlists(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReleaseWatchlistListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.post("/release-watchlists/watchlists", response_model=ScanApiV1Envelope)
def v1_create_release_watchlist(
    payload: ReleaseWatchlistCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_watchlist(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.post("/release-watchlists/watchlists/{watchlist_id}/items", response_model=ScanApiV1Envelope)
def v1_add_release_watchlist_item(
    watchlist_id: int,
    payload: ReleaseWatchlistItemCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = add_watchlist_item(
            session,
            owner_user_id=int(current_user.id),
            watchlist_id=watchlist_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.delete("/release-watchlists/watchlists/{watchlist_id}/items/{item_id}", response_model=ScanApiV1Envelope)
def v1_delete_release_watchlist_item(
    watchlist_id: int,
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        remove_watchlist_item(session, owner_user_id=int(current_user.id), watchlist_id=watchlist_id, item_id=item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(DeleteWatchlistItemResponse(item_id=item_id, deleted=True), owner_user_id=int(current_user.id))


@release_watchlists_v1_router.get("/release-watchlists/dashboard", response_model=ScanApiV1Envelope)
def v1_release_watchlist_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_continuity_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.post("/release-watchlists/run/continuity", response_model=ScanApiV1Envelope)
def v1_run_release_continuity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    runs, alerts, execution = run_continuity_detection(session, owner_user_id=int(current_user.id))
    body = WatchlistAlertsRunResponse(runs=runs, alerts=alerts, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.post("/release-watchlists/run/foc-reminders", response_model=ScanApiV1Envelope)
def v1_run_foc_reminders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    reminders, execution = run_foc_reminders(session, owner_user_id=int(current_user.id))
    body = WatchlistRemindersRunResponse(reminders=reminders, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.post("/release-watchlists/run/release-reminders", response_model=ScanApiV1Envelope)
def v1_run_release_reminders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    reminders, execution = run_release_reminders(session, owner_user_id=int(current_user.id))
    body = WatchlistRemindersRunResponse(reminders=reminders, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_watchlists_v1_router.post("/release-watchlists/run/auto-watchlists", response_model=ScanApiV1Envelope)
def v1_run_auto_watchlists(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    watchlists, execution = run_auto_watchlists(session, owner_user_id=int(current_user.id))
    body = AutoWatchlistsRunResponse(watchlists=watchlists, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))
