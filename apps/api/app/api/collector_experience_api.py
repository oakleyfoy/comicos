"""P65 Collector Experience APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.collector_experience import (
    AutomationRunAllRead,
    AutomationRunRead,
    AutomationRunsListRead,
    AutomationSubscriptionRead,
    AutomationSubscriptionsListRead,
    CollectorBulkUpdateRead,
    CollectorNarrativeItemRead,
    CollectorNarrativeSnapshotRead,
    CollectorTaskBuildResultRead,
    CollectorTaskBulkPatch,
    CollectorTaskHistoryEntryRead,
    CollectorTaskHistoryListRead,
    CollectorTaskItemRead,
    CollectorTaskSnapshotRead,
    CollectorTaskStatusPatch,
    NarrativeBuildResultRead,
    NotificationBuildResultRead,
    NotificationItemRead,
    NotificationSnapshotRead,
    NotificationStatusPatch,
    P65CertificationRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.collector_automation_service import (
    ensure_default_subscriptions,
    list_recent_runs,
    list_subscriptions,
    run_all_enabled_automations,
    run_automation,
)
from app.services.collector_narrative_service import (
    READINESS_NOT_READY as NARR_NOT_READY,
    build_collector_narratives,
    get_latest_narrative_snapshot,
    list_narrative_items,
)
from app.services.collector_workspace_service import (
    READINESS_NOT_READY,
    READINESS_SUCCESS,
    build_collector_tasks,
    bulk_update_task_status,
    get_latest_task_snapshot,
    get_task_item,
    list_task_history,
    list_task_items,
    update_task_status,
)
from app.services.notification_center_service import (
    build_notifications,
    get_latest_notification_snapshot,
    list_notification_items,
    update_notification_status,
)
from app.services.p65_collector_experience_certification import certify_p65_collector_experience
from app.services.p65_feature_flags import (
    p65_automation_enabled,
    p65_collector_workspace_enabled,
    p65_notification_center_enabled,
)

workspace_router = APIRouter(prefix="/api/v1/collector-workspace", tags=["P65 Collector Workspace"])
narratives_router = APIRouter(prefix="/api/v1/collector-narratives", tags=["P65 Collector Narratives"])
automation_router = APIRouter(prefix="/api/v1/collector-automation", tags=["P65 Collector Automation"])
notifications_router = APIRouter(prefix="/api/v1/notifications", tags=["P65 Notification Center"])


def attach_collector_experience_layer(app: FastAPI) -> None:
    app.include_router(workspace_router)
    app.include_router(narratives_router)
    app.include_router(automation_router)
    app.include_router(notifications_router)


def _ws_guard() -> None:
    if not p65_collector_workspace_enabled():
        raise HTTPException(status_code=403, detail="P65_COLLECTOR_WORKSPACE_DISABLED")


def _auto_guard() -> None:
    if not p65_automation_enabled():
        raise HTTPException(status_code=403, detail="P65_AUTOMATION_DISABLED")


def _notif_guard() -> None:
    if not p65_notification_center_enabled():
        raise HTTPException(status_code=403, detail="P65_NOTIFICATION_CENTER_DISABLED")


def _task_read(row) -> CollectorTaskItemRead:
    return CollectorTaskItemRead(
        id=int(row.id or 0),
        snapshot_id=int(row.snapshot_id),
        task_type=row.task_type,
        status=row.status,
        title=row.title,
        publisher=row.publisher,
        issue_number=row.issue_number,
        priority_score=row.priority_score,
        source_system=row.source_system,
        source_ref_json=row.source_ref_json or {},
        explanation=row.explanation,
        action_hint=row.action_hint,
        updated_at=row.updated_at,
    )


@workspace_router.get("/tasks/latest", response_model=ScanApiV1Envelope)
def tasks_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    task_type: str | None = Query(default=None),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    snap = get_latest_task_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(CollectorTaskSnapshotRead(readiness_status=READINESS_NOT_READY), owner_user_id=int(current_user.id))
    items = list_task_items(session, snapshot_id=int(snap.id or 0), task_type=task_type)
    by_type: dict[str, int] = {}
    for it in items:
        by_type[it.task_type] = by_type.get(it.task_type, 0) + 1
    body = CollectorTaskSnapshotRead(
        snapshot_id=int(snap.id or 0),
        readiness_status=READINESS_SUCCESS,
        generated_at=snap.generated_at,
        total_items=snap.total_items,
        items=[_task_read(i) for i in items],
        by_type=by_type,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@workspace_router.post("/tasks/build", response_model=ScanApiV1Envelope)
def tasks_build(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    snap = build_collector_tasks(session, owner_user_id=int(current_user.id))
    return wrap_object(
        CollectorTaskBuildResultRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items),
        owner_user_id=int(current_user.id),
    )


@workspace_router.get("/tasks/history", response_model=ScanApiV1Envelope)
def tasks_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    rows = list_task_history(session, owner_user_id=int(current_user.id))
    body = [
        CollectorTaskHistoryEntryRead(
            snapshot_id=int(r.id or 0),
            generated_at=r.generated_at,
            total_items=r.total_items,
        )
        for r in rows
    ]
    return wrap_object(CollectorTaskHistoryListRead(entries=body), owner_user_id=int(current_user.id))


@workspace_router.patch("/tasks/bulk", response_model=ScanApiV1Envelope)
def tasks_bulk_patch(
    payload: CollectorTaskBulkPatch,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    n = bulk_update_task_status(
        session,
        owner_user_id=int(current_user.id),
        task_ids=payload.task_ids,
        status=payload.status,
    )
    return wrap_object(CollectorBulkUpdateRead(updated=n), owner_user_id=int(current_user.id))


@workspace_router.patch("/tasks/{task_id}", response_model=ScanApiV1Envelope)
def tasks_patch(
    task_id: int,
    payload: CollectorTaskStatusPatch,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    row = update_task_status(
        session,
        owner_user_id=int(current_user.id),
        task_id=task_id,
        status=payload.status,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="TASK_NOT_FOUND")
    return wrap_object(_task_read(row), owner_user_id=int(current_user.id))


@workspace_router.get("/platform/certification", response_model=ScanApiV1Envelope)
def platform_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    data = certify_p65_collector_experience(session, owner_user_id=int(current_user.id))
    return wrap_object(P65CertificationRead(**data), owner_user_id=int(current_user.id))


@narratives_router.get("/latest", response_model=ScanApiV1Envelope)
def narratives_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    snap = get_latest_narrative_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(CollectorNarrativeSnapshotRead(readiness_status=NARR_NOT_READY), owner_user_id=int(current_user.id))
    items = list_narrative_items(session, snapshot_id=int(snap.id or 0))
    body = CollectorNarrativeSnapshotRead(
        snapshot_id=int(snap.id or 0),
        readiness_status=snap.readiness_status,
        week_start=snap.week_start,
        briefing_markdown=snap.briefing_markdown,
        items=[
            CollectorNarrativeItemRead(
                id=int(i.id or 0),
                narrative_kind=i.narrative_kind,
                title=i.title,
                narrative_text=i.narrative_text,
                signal_citations_json=list(i.signal_citations_json or []),
            )
            for i in items
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@narratives_router.post("/build", response_model=ScanApiV1Envelope)
def narratives_build(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _ws_guard()
    assert current_user.id is not None
    snap = build_collector_narratives(session, owner_user_id=int(current_user.id))
    return wrap_object(
        NarrativeBuildResultRead(snapshot_id=int(snap.id or 0), readiness_status=snap.readiness_status),
        owner_user_id=int(current_user.id),
    )


@automation_router.get("/subscriptions", response_model=ScanApiV1Envelope)
def automation_subscriptions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _auto_guard()
    assert current_user.id is not None
    ensure_default_subscriptions(session, owner_user_id=int(current_user.id))
    subs = list_subscriptions(session, owner_user_id=int(current_user.id))
    body = [
        AutomationSubscriptionRead(
            id=int(s.id or 0),
            automation_kind=s.automation_kind,
            delivery_type=s.delivery_type,
            enabled=s.enabled,
            config_json=s.config_json or {},
        )
        for s in subs
    ]
    return wrap_object(AutomationSubscriptionsListRead(subscriptions=body), owner_user_id=int(current_user.id))


@automation_router.get("/runs/latest", response_model=ScanApiV1Envelope)
def automation_runs_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _auto_guard()
    assert current_user.id is not None
    runs = list_recent_runs(session, owner_user_id=int(current_user.id))
    body = [
        AutomationRunRead(
            id=int(r.id or 0),
            automation_kind=r.automation_kind,
            delivery_type=r.delivery_type,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            details_json=r.details_json or {},
        )
        for r in runs
    ]
    return wrap_object(AutomationRunsListRead(runs=body), owner_user_id=int(current_user.id))


@automation_router.post("/run/{automation_kind}", response_model=ScanApiV1Envelope)
def automation_run_kind(
    automation_kind: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _auto_guard()
    assert current_user.id is not None
    run = run_automation(session, owner_user_id=int(current_user.id), automation_kind=automation_kind)
    return wrap_object(
        AutomationRunRead(
            id=int(run.id or 0),
            automation_kind=run.automation_kind,
            delivery_type=run.delivery_type,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            details_json=run.details_json or {},
        ),
        owner_user_id=int(current_user.id),
    )


@automation_router.post("/run-all", response_model=ScanApiV1Envelope)
def automation_run_all(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _auto_guard()
    assert current_user.id is not None
    runs = run_all_enabled_automations(session, owner_user_id=int(current_user.id))
    return wrap_object(AutomationRunAllRead(run_count=len(runs)), owner_user_id=int(current_user.id))


@notifications_router.get("/latest", response_model=ScanApiV1Envelope)
def notifications_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _notif_guard()
    assert current_user.id is not None
    snap = get_latest_notification_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(NotificationSnapshotRead(readiness_status=READINESS_NOT_READY), owner_user_id=int(current_user.id))
    items = list_notification_items(session, snapshot_id=int(snap.id or 0))
    body = NotificationSnapshotRead(
        snapshot_id=int(snap.id or 0),
        readiness_status=READINESS_SUCCESS,
        unread_count=snap.unread_count,
        total_items=snap.total_items,
        items=[
            NotificationItemRead(
                id=int(i.id or 0),
                notification_type=i.notification_type,
                status=i.status,
                title=i.title,
                message=i.message,
                deep_link=i.deep_link,
                created_at=i.created_at,
            )
            for i in items
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@notifications_router.post("/build", response_model=ScanApiV1Envelope)
def notifications_build(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _notif_guard()
    assert current_user.id is not None
    snap = build_notifications(session, owner_user_id=int(current_user.id))
    return wrap_object(
        NotificationBuildResultRead(
            snapshot_id=int(snap.id or 0),
            unread_count=snap.unread_count,
            total_items=snap.total_items,
        ),
        owner_user_id=int(current_user.id),
    )


@notifications_router.patch("/items/{item_id}", response_model=ScanApiV1Envelope)
def notifications_patch(
    item_id: int,
    payload: NotificationStatusPatch,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _notif_guard()
    assert current_user.id is not None
    row = update_notification_status(
        session,
        owner_user_id=int(current_user.id),
        item_id=item_id,
        status=payload.status,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="NOTIFICATION_NOT_FOUND")
    return wrap_object(
        NotificationItemRead(
            id=int(row.id or 0),
            notification_type=row.notification_type,
            status=row.status,
            title=row.title,
            message=row.message,
            deep_link=row.deep_link,
            created_at=row.created_at,
        ),
        owner_user_id=int(current_user.id),
    )
