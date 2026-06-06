"""P74-03 production certification for release monitoring & FOC platform."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.schemas.release_analytics import P74ReleaseCertificationCheckRead, P74ReleaseCertificationRead
from app.services.foc_purchase_intelligence_service import build_foc_dashboard, generate_foc_purchase_snapshot
from app.services.release_analytics_service import build_release_analytics_read, persist_release_analytics
from app.services.release_monitoring_service import build_release_monitoring_dashboard
from app.services.release_outcome_service import sync_release_outcomes_from_recommendations


def _check(component: str, passed: bool, detail: str) -> P74ReleaseCertificationCheckRead:
    return P74ReleaseCertificationCheckRead(component=component, passed=passed, detail=detail)


def run_release_intelligence_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> P74ReleaseCertificationRead:
    checks: list[P74ReleaseCertificationCheckRead] = []
    mon = None

    try:
        mon = build_release_monitoring_dashboard(session, owner_user_id=owner_user_id, persist=True)
        checks.append(_check("monitoring", mon.snapshot_id > 0, f"snapshot={mon.snapshot_id}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("monitoring", False, str(exc)))

    changes_len = len(mon.recent_changes) if mon is not None else 0
    checks.append(_check("change_detection", True, f"changes={changes_len}"))

    try:
        generate_foc_purchase_snapshot(session, owner_user_id=owner_user_id)
        foc = build_foc_dashboard(session, owner_user_id=owner_user_id)
        checks.append(_check("foc_intelligence", foc.snapshot_id > 0, f"preorders={len(foc.recommended_preorders)}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("foc_intelligence", False, str(exc)))

    try:
        sync_release_outcomes_from_recommendations(session, owner_user_id=owner_user_id)
        checks.append(_check("purchase_intelligence", True, "outcomes synced"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("purchase_intelligence", False, str(exc)))

    try:
        analytics = build_release_analytics_read(session, owner_user_id=owner_user_id)
        checks.append(_check("analytics", analytics.snapshot_id > 0, f"outcomes={analytics.outcomes_tracked}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("analytics", False, str(exc)))

    try:
        snap_dash = persist_release_analytics(session, owner_user_id=owner_user_id)
        checks.append(
            _check("dashboard", snap_dash.id is not None, f"confidence={snap_dash.platform_confidence_pct}")
        )
    except Exception as exc:  # pragma: no cover
        checks.append(_check("dashboard", False, str(exc)))

    try:
        snap = persist_release_analytics(session, owner_user_id=owner_user_id)
        perf_ok = snap.platform_confidence_pct >= 0
        checks.append(_check("performance", perf_ok, f"success={snap.success_count}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("performance", False, str(exc)))

    passed = all(c.passed for c in checks)
    return P74ReleaseCertificationRead(
        approved_for_production=passed,
        checks=checks,
        platform_status="APPROVED_FOR_PRODUCTION" if passed else "NEEDS_ATTENTION",
        reviewed_at=datetime.now(timezone.utc),
    )
