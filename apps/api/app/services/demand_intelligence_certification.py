"""P61 platform component certification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.schemas.demand_intelligence import DemandPlatformCertificationBundleRead, PlatformCertificationRead
from app.services.demand_refresh_service import count_issue_snapshots, get_latest_refresh_run
from app.services.demand_velocity_service import count_velocity_snapshots
from app.services.spec_opportunity_service import get_latest_spec_snapshot
from app.services.weekly_demand_automation_service import list_capture_schedule
from app.models.demand_intelligence import CAPTURE_STATUS_CERTIFIED, REFRESH_STATUS_SUCCESS


def _cert(
    *,
    component: str,
    certified: bool,
    status: str,
    summary: str,
    notes: list[str],
) -> PlatformCertificationRead:
    return PlatformCertificationRead(
        component=component,
        certified=certified,
        status=status,
        summary=summary,
        notes=notes,
        checked_at=datetime.now(timezone.utc),
    )


def certify_refresh(session: Session) -> PlatformCertificationRead:
    latest = get_latest_refresh_run(session)
    snap_count = count_issue_snapshots(session)
    notes: list[str] = []
    ok = False
    if latest is None:
        notes.append("No demand_refresh_run recorded yet.")
        status = "NOT_READY"
    elif latest.status != REFRESH_STATUS_SUCCESS:
        notes.append(f"Latest refresh status is {latest.status}.")
        status = "WARNING"
    else:
        ok = snap_count > 0
        status = "PASS" if ok else "WARNING"
        if snap_count == 0:
            notes.append("No issue_demand_snapshot rows.")
        else:
            notes.append(f"{snap_count} issue snapshots; last refresh issues={latest.issues_refreshed}.")
    return _cert(
        component="P61-01_REFRESH",
        certified=ok,
        status=status,
        summary="Demand refresh certified" if ok else "Demand refresh not certified",
        notes=notes,
    )


def certify_velocity(session: Session) -> PlatformCertificationRead:
    count = count_velocity_snapshots(session)
    ok = count > 0
    notes = [f"{count} demand_velocity_snapshot rows."]
    if not ok:
        notes.append("Run POST /velocity/compute after demand refresh.")
    return _cert(
        component="P61-02_VELOCITY",
        certified=ok,
        status="PASS" if ok else "NOT_READY",
        summary="Velocity certified" if ok else "Velocity not ready",
        notes=notes,
    )


def certify_spec(session: Session, *, owner_user_id: int) -> PlatformCertificationRead:
    snap = get_latest_spec_snapshot(session, owner_user_id=owner_user_id)
    ok = snap is not None and snap.row_count > 0
    notes: list[str] = []
    if snap is None:
        notes.append("No spec_opportunity_snapshot for owner.")
        status = "NOT_READY"
    else:
        status = "PASS" if ok else "WARNING"
        notes.append(f"Latest snapshot rows={snap.row_count} at {snap.snapshot_at.isoformat()}.")
    return _cert(
        component="P61-03_SPEC",
        certified=ok,
        status=status,
        summary="Spec opportunities certified" if ok else "Spec opportunities not ready",
        notes=notes,
    )


def certify_automation(session: Session) -> PlatformCertificationRead:
    rows = list_capture_schedule(session)
    certified_rows = [r for r in rows if r.status == CAPTURE_STATUS_CERTIFIED]
    ok = len(certified_rows) >= 1
    notes = [f"Schedule rows={len(rows)}; certified={len(certified_rows)}."]
    return _cert(
        component="P61-04_AUTOMATION",
        certified=ok,
        status="PASS" if ok else "NOT_READY",
        summary="Weekly automation certified" if ok else "Weekly automation not ready",
        notes=notes,
    )


def get_demand_platform_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> DemandPlatformCertificationBundleRead:
    refresh = certify_refresh(session)
    velocity = certify_velocity(session)
    spec = certify_spec(session, owner_user_id=owner_user_id)
    automation = certify_automation(session)
    ready = refresh.certified and velocity.certified and spec.certified
    return DemandPlatformCertificationBundleRead(
        refresh=refresh,
        velocity=velocity,
        spec=spec,
        automation=automation,
        platform_ready=ready,
    )
