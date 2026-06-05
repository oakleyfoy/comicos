"""P61 Demand Intelligence Platform APIs."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.demand_intelligence import (
    DemandRefreshRun,
    DemandVelocitySnapshot,
    IssueDemandSnapshot,
    SpecOpportunityRow,
    WeeklyDemandCaptureSchedule,
)
from app.schemas.demand_intelligence import (
    AutomationDiscoverRead,
    DemandDashboardRead,
    DemandPlatformCertificationBundleRead,
    DemandRefreshRequest,
    DemandRefreshRunRead,
    DemandVelocityComputeRequest,
    DemandVelocitySnapshotRead,
    IssueDemandSnapshotRead,
    PaginatedIssueDemandList,
    PaginatedScheduleList,
    PaginatedVelocityList,
    SpecBuildResultRead,
    SpecOpportunityBuildRequest,
    SpecOpportunityRowRead,
    SpecOpportunitySnapshotRead,
    VelocityComputeResultRead,
    WeeklyCaptureScheduleRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.demand_intelligence_certification import get_demand_platform_certification
from app.services.demand_refresh_service import (
    build_demand_dashboard,
    get_latest_refresh_run,
    list_issue_demand_snapshots,
    run_demand_refresh,
)
from app.services.demand_velocity_service import compute_demand_velocity, list_velocity_snapshots
from app.services.spec_opportunity_service import build_spec_opportunities, list_spec_opportunity_rows
from app.services.weekly_demand_automation_service import (
    discover_capture_schedule,
    list_capture_schedule,
    run_post_capture_pipeline,
    sync_schedule_from_catalog,
)


def _refresh_read(row: DemandRefreshRun) -> DemandRefreshRunRead:
    return DemandRefreshRunRead(
        id=int(row.id or 0),
        trigger_type=row.trigger_type,
        scope=row.scope,
        owner_user_id=row.owner_user_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        status=row.status,
        profiles_updated=row.profiles_updated,
        issues_refreshed=row.issues_refreshed,
        signals_appended=row.signals_appended,
        source_version=row.source_version,
        details_json=row.details_json or {},
    )


def _issue_read(row: IssueDemandSnapshot) -> IssueDemandSnapshotRead:
    return IssueDemandSnapshotRead(
        id=int(row.id or 0),
        source_name=row.source_name,
        external_issue_id=row.external_issue_id,
        release_issue_id=row.release_issue_id,
        title=row.title,
        pull_count=row.pull_count,
        want_count=row.want_count,
        community_demand_score=row.community_demand_score,
        entity_rollup_score=row.entity_rollup_score,
        combined_demand_score=row.combined_demand_score,
        confidence_score=row.confidence_score,
        signal_sources_json=row.signal_sources_json or {},
        source_version=row.source_version,
        refreshed_at=row.refreshed_at,
    )


def _velocity_read(row: DemandVelocitySnapshot) -> DemandVelocitySnapshotRead:
    return DemandVelocitySnapshotRead(
        id=int(row.id or 0),
        release_issue_id=row.release_issue_id,
        external_issue_id=row.external_issue_id,
        window_days=row.window_days,
        pull_delta=row.pull_delta,
        want_delta=row.want_delta,
        combined_score_delta=row.combined_score_delta,
        velocity_score=row.velocity_score,
        acceleration_score=row.acceleration_score,
        trend_label=row.trend_label,
        confidence_score=row.confidence_score,
        computed_at=row.computed_at,
    )


demand_v1_router = APIRouter(prefix="/api/v1/demand", tags=["P61 Demand Refresh"])
velocity_v1_router = APIRouter(prefix="/api/v1/velocity", tags=["P61 Demand Velocity"])
spec_v1_router = APIRouter(prefix="/api/v1/spec", tags=["P61 Spec Opportunities"])
automation_v1_router = APIRouter(prefix="/api/v1/automation", tags=["P61 Weekly Automation"])


def attach_demand_intelligence_platform_layer(app: FastAPI) -> None:
    app.include_router(demand_v1_router)
    app.include_router(velocity_v1_router)
    app.include_router(spec_v1_router)
    app.include_router(automation_v1_router)


@demand_v1_router.get("/dashboard", response_model=ScanApiV1Envelope)
def v1_demand_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    raw = build_demand_dashboard(session)
    latest = raw.get("latest_refresh")
    body = DemandDashboardRead(
        latest_refresh=_refresh_read(latest) if isinstance(latest, DemandRefreshRun) else None,
        issue_snapshot_count=int(raw.get("issue_snapshot_count") or 0),
        velocity_snapshot_count=int(raw.get("velocity_snapshot_count") or 0),
        top_demand_issues=[_issue_read(r) for r in raw.get("top_demand_issues") or []],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@demand_v1_router.get("/issues", response_model=ScanApiV1Envelope)
def v1_demand_issues(
    limit: int = 50,
    offset: int = 0,
    release_issue_id: int | None = None,
    min_combined_score: float | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    rows, total = list_issue_demand_snapshots(
        session,
        limit=lim,
        offset=off,
        release_issue_id=release_issue_id,
        min_combined_score=min_combined_score,
    )
    body = PaginatedIssueDemandList(
        items=[_issue_read(r) for r in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@demand_v1_router.get("/runs/latest", response_model=ScanApiV1Envelope)
def v1_demand_runs_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    latest = get_latest_refresh_run(session)
    if latest is None:
        raise HTTPException(status_code=404, detail="No demand refresh runs")
    return wrap_object(_refresh_read(latest), owner_user_id=int(current_user.id))


@demand_v1_router.post("/refresh", response_model=ScanApiV1Envelope)
def v1_demand_refresh(
    payload: DemandRefreshRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    run = run_demand_refresh(
        session,
        scope=payload.scope,
        days_forward=payload.days_forward,
        owner_user_id=payload.owner_user_id or int(current_user.id),
        refresh_locg=False,
    )
    return wrap_object(_refresh_read(run), owner_user_id=int(current_user.id))


@demand_v1_router.get("/certification", response_model=ScanApiV1Envelope)
def v1_demand_refresh_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    from app.services.demand_intelligence_certification import certify_refresh

    assert current_user.id is not None
    return wrap_object(certify_refresh(session), owner_user_id=int(current_user.id))


@velocity_v1_router.get("/issues", response_model=ScanApiV1Envelope)
def v1_velocity_issues(
    window_days: int = 7,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_velocity_snapshots(session, window_days=window_days, limit=limit, offset=offset)
    body = PaginatedVelocityList(
        items=[_velocity_read(r) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@velocity_v1_router.post("/compute", response_model=ScanApiV1Envelope)
def v1_velocity_compute(
    payload: DemandVelocityComputeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    updated = 0
    for window in payload.window_days or [7, 14, 28]:
        updated += compute_demand_velocity(session, window_days=int(window))
    return wrap_object(
        VelocityComputeResultRead(rows_updated=updated, windows=list(payload.window_days or [7, 14, 28])),
        owner_user_id=int(current_user.id),
    )


@velocity_v1_router.get("/certification", response_model=ScanApiV1Envelope)
def v1_velocity_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    from app.services.demand_intelligence_certification import certify_velocity

    assert current_user.id is not None
    return wrap_object(certify_velocity(session), owner_user_id=int(current_user.id))


@spec_v1_router.get("/latest", response_model=ScanApiV1Envelope)
def v1_spec_latest(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, snapshot = list_spec_opportunity_rows(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="NOT_READY", headers={"X-ComicOS-Reason": "NO_SPEC_SNAPSHOT"})
    body = SpecOpportunitySnapshotRead(
        id=int(snapshot.id or 0),
        owner_user_id=snapshot.owner_user_id,
        snapshot_at=snapshot.snapshot_at,
        engine_epoch=snapshot.engine_epoch,
        row_count=snapshot.row_count,
        rows=[
            SpecOpportunityRowRead(
                id=int(r.id or 0),
                release_issue_id=r.release_issue_id,
                title=r.title,
                opportunity_score=r.opportunity_score,
                spec_baseline_score=r.spec_baseline_score,
                demand_score=r.demand_score,
                velocity_score=r.velocity_score,
                preference_fit_score=r.preference_fit_score,
                horizon_bucket=r.horizon_bucket,
                rationale_json=r.rationale_json or {},
                rank=r.rank,
            )
            for r in rows
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_v1_router.post("/build", response_model=ScanApiV1Envelope)
def v1_spec_build(
    payload: SpecOpportunityBuildRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    snapshot = build_spec_opportunities(
        session,
        owner_user_id=int(current_user.id),
        limit=payload.limit,
    )
    return wrap_object(
        SpecBuildResultRead(snapshot_id=int(snapshot.id or 0), row_count=snapshot.row_count),
        owner_user_id=int(current_user.id),
    )


@spec_v1_router.get("/certification", response_model=ScanApiV1Envelope)
def v1_spec_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    from app.services.demand_intelligence_certification import certify_spec

    assert current_user.id is not None
    return wrap_object(certify_spec(session, owner_user_id=int(current_user.id)), owner_user_id=int(current_user.id))


@automation_v1_router.get("/schedule", response_model=ScanApiV1Envelope)
def v1_automation_schedule(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows = list_capture_schedule(session)
    items = [
        WeeklyCaptureScheduleRead(
            id=int(r.id or 0),
            release_date=r.release_date,
            status=r.status,
            owner_user_id=r.owner_user_id,
            certification_path=r.certification_path,
            sync_run_id=r.sync_run_id,
            details_json=r.details_json or {},
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return wrap_standard_list(
        PaginatedScheduleList(items=items, total_items=len(items), limit=len(items), offset=0),
        owner_user_id=int(current_user.id),
    )


@automation_v1_router.post("/discover", response_model=ScanApiV1Envelope)
def v1_automation_discover(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows = discover_capture_schedule(session, owner_user_id=int(current_user.id))
    sync_schedule_from_catalog(session)
    return wrap_object(AutomationDiscoverRead(schedule_rows=len(rows)), owner_user_id=int(current_user.id))


@automation_v1_router.post("/schedule/{release_date}/run", response_model=ScanApiV1Envelope)
def v1_automation_run(
    release_date: date,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    from sqlmodel import select

    assert current_user.id is not None
    row = session.exec(
        select(WeeklyDemandCaptureSchedule).where(WeeklyDemandCaptureSchedule.release_date == release_date)
    ).first()
    if row is None:
        row = discover_capture_schedule(session, owner_user_id=int(current_user.id))[0]
    updated = run_post_capture_pipeline(session, schedule=row, owner_user_id=int(current_user.id))
    return wrap_object(
        WeeklyCaptureScheduleRead(
            id=int(updated.id or 0),
            release_date=updated.release_date,
            status=updated.status,
            owner_user_id=updated.owner_user_id,
            certification_path=updated.certification_path,
            sync_run_id=updated.sync_run_id,
            details_json=updated.details_json or {},
            updated_at=updated.updated_at,
        ),
        owner_user_id=int(current_user.id),
    )


@automation_v1_router.get("/certification", response_model=ScanApiV1Envelope)
def v1_automation_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    from app.services.demand_intelligence_certification import certify_automation

    assert current_user.id is not None
    return wrap_object(certify_automation(session), owner_user_id=int(current_user.id))


@demand_v1_router.get("/platform/certification", response_model=ScanApiV1Envelope)
def v1_platform_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    bundle: DemandPlatformCertificationBundleRead = get_demand_platform_certification(
        session,
        owner_user_id=int(current_user.id),
    )
    return wrap_object(bundle, owner_user_id=int(current_user.id))
