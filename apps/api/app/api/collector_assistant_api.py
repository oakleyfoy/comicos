"""P64 Collector Assistant API (Phase A)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.collector_assistant import RUN_STATUS_NOT_READY, RUN_STATUS_SUCCESS
from app.schemas.collector_assistant import (
    CollectorAlertRead,
    CollectorAlertsRead,
    CollectorBriefingRead,
    CollectorBuildResultRead,
    CollectorDashboardRead,
    CollectorHealthRead,
    CollectorPlatformCertificationRead,
    CollectorRecommendationItemRead,
    CollectorRecommendationsRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.collector_assistant_certification_service import get_collector_assistant_platform_certification
from app.services.collector_assistant_orchestrator import (
    get_latest_alert_snapshot,
    get_latest_briefing,
    get_latest_executive,
    get_latest_health,
    get_latest_run,
    list_alerts_for_snapshot,
    list_all_recommendations_for_run,
    run_collector_assistant_build,
)
from app.services.p64_feature_flags import p64_collector_assistant_enabled

collector_assistant_router = APIRouter(
    prefix="/api/v1/collector-assistant",
    tags=["P64 Collector Assistant"],
)


def attach_collector_assistant_layer(app: FastAPI) -> None:
    app.include_router(collector_assistant_router)


def _guard() -> None:
    if not p64_collector_assistant_enabled():
        raise HTTPException(status_code=403, detail="P64_COLLECTOR_ASSISTANT_DISABLED")


def _item_read(row) -> CollectorRecommendationItemRead:
    return CollectorRecommendationItemRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        lane=row.lane,
        priority_score=row.priority_score,
        confidence=row.confidence,
        title=row.title,
        publisher=row.publisher,
        issue_number=row.issue_number,
        recommended_action=row.recommended_action,
        explanation=row.explanation,
        reason_codes=list(row.reason_codes_json or []),
        release_issue_id=row.release_issue_id,
        inventory_copy_id=row.inventory_copy_id,
        status=row.status,
    )


@collector_assistant_router.get("/briefing/latest", response_model=ScanApiV1Envelope)
def v1_briefing_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    row = get_latest_briefing(session, owner_user_id=int(current_user.id))
    if row is None:
        body = CollectorBriefingRead(readiness_status=RUN_STATUS_NOT_READY, headline="No briefing yet")
        return wrap_object(body, owner_user_id=int(current_user.id))
    headline = str((row.briefing_json or {}).get("headline", ""))
    body = CollectorBriefingRead(
        snapshot_id=int(row.id or 0),
        run_id=int(row.run_id),
        readiness_status=row.readiness_status,
        week_start=row.week_start,
        headline=headline,
        briefing_json=row.briefing_json or {},
        briefing_markdown=row.briefing_markdown or "",
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@collector_assistant_router.post("/briefing/build", response_model=ScanApiV1Envelope)
def v1_briefing_build(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    run = run_collector_assistant_build(session, owner_user_id=int(current_user.id), scope="full")
    return wrap_object(
        CollectorBuildResultRead(run_id=int(run.id or 0), status=run.status),
        owner_user_id=int(current_user.id),
    )


@collector_assistant_router.get("/recommendations/latest", response_model=ScanApiV1Envelope)
def v1_recommendations_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    run = get_latest_run(session, owner_user_id=int(current_user.id))
    if run is None or run.status != RUN_STATUS_SUCCESS:
        body = CollectorRecommendationsRead(readiness_status=RUN_STATUS_NOT_READY)
        return wrap_object(body, owner_user_id=int(current_user.id))
    lanes_raw = list_all_recommendations_for_run(session, run_id=int(run.id or 0))
    lanes = {lane: [_item_read(i) for i in items] for lane, items in lanes_raw.items()}
    total = sum(len(v) for v in lanes.values())
    body = CollectorRecommendationsRead(
        run_id=int(run.id or 0),
        readiness_status=run.status,
        lanes=lanes,
        total_items=total,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@collector_assistant_router.post("/recommendations/build", response_model=ScanApiV1Envelope)
def v1_recommendations_build(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    run = run_collector_assistant_build(session, owner_user_id=int(current_user.id), scope="lanes")
    return wrap_object(
        CollectorBuildResultRead(run_id=int(run.id or 0), status=run.status),
        owner_user_id=int(current_user.id),
    )


@collector_assistant_router.get("/health/latest", response_model=ScanApiV1Envelope)
def v1_health_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    row = get_latest_health(session, owner_user_id=int(current_user.id))
    if row is None:
        return wrap_object(CollectorHealthRead(readiness_status=RUN_STATUS_NOT_READY), owner_user_id=int(current_user.id))
    body = CollectorHealthRead(
        snapshot_id=int(row.id or 0),
        readiness_status=row.readiness_status,
        health_score=float(row.health_score),
        health_band=row.health_band,
        metrics_json=row.metrics_json or {},
        risk_flags_json=list(row.risk_flags_json or []),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@collector_assistant_router.get("/alerts/latest", response_model=ScanApiV1Envelope)
def v1_alerts_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    snap = get_latest_alert_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(CollectorAlertsRead(readiness_status=RUN_STATUS_NOT_READY), owner_user_id=int(current_user.id))
    alerts = list_alerts_for_snapshot(session, alert_snapshot_id=int(snap.id or 0))
    body = CollectorAlertsRead(
        snapshot_id=int(snap.id or 0),
        alert_count=snap.alert_count,
        critical_count=snap.critical_count,
        readiness_status=RUN_STATUS_SUCCESS,
        alerts=[
            CollectorAlertRead(
                id=int(a.id or 0),
                alert_type=a.alert_type,
                severity=a.severity,
                title=a.title,
                message=a.message,
                action_deep_link=a.action_deep_link,
            )
            for a in alerts
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@collector_assistant_router.get("/dashboard/latest", response_model=ScanApiV1Envelope)
def v1_dashboard_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    row = get_latest_executive(session, owner_user_id=int(current_user.id))
    if row is None:
        return wrap_object(CollectorDashboardRead(readiness_status=RUN_STATUS_NOT_READY), owner_user_id=int(current_user.id))
    body = CollectorDashboardRead(
        bundle_id=int(row.id or 0),
        run_id=int(row.run_id),
        readiness_status=row.readiness_status,
        platform_ready=row.platform_ready,
        dashboard_json=row.dashboard_json or {},
        freshness_json=row.freshness_json or {},
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@collector_assistant_router.post("/platform/build", response_model=ScanApiV1Envelope)
def v1_platform_build(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    run = run_collector_assistant_build(session, owner_user_id=int(current_user.id), scope="full")
    return wrap_object(
        CollectorBuildResultRead(run_id=int(run.id or 0), status=run.status),
        owner_user_id=int(current_user.id),
    )


@collector_assistant_router.get("/platform/certification", response_model=ScanApiV1Envelope)
def v1_platform_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    cert = get_collector_assistant_platform_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(CollectorPlatformCertificationRead(**cert), owner_user_id=int(current_user.id))
