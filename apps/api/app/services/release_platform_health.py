from __future__ import annotations

from collections import Counter

from sqlmodel import Session, func, select

from app.models.lunar_feed import LunarFeedRun
from app.models.lunar_scheduler import LunarScheduleConfig, LunarScheduledRun
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseVariant
from app.models.release_watchlist import ReleaseWatchlist
from app.models.spec_intelligence import SpecRecommendation
from app.schemas.release_platform_certification import ReleasePlatformHealthComponentRead, ReleasePlatformHealthRead
from app.services.lunar_credentials import get_credential_status
from app.services.release_horizon_engine import build_release_horizons

HEALTH_STATUS_HEALTHY = "HEALTHY"
HEALTH_STATUS_WARNING = "WARNING"
HEALTH_STATUS_FAILED = "FAILED"
HEALTH_STATUS_DISABLED = "DISABLED"


def _aggregate_health(statuses: list[str]) -> str:
    if any(status == HEALTH_STATUS_FAILED for status in statuses):
        return HEALTH_STATUS_FAILED
    if any(status == HEALTH_STATUS_WARNING for status in statuses):
        return HEALTH_STATUS_WARNING
    if statuses and all(status == HEALTH_STATUS_DISABLED for status in statuses):
        return HEALTH_STATUS_DISABLED
    return HEALTH_STATUS_HEALTHY


def _component(
    *,
    component_code: str,
    title: str,
    health_status: str,
    summary: str,
    details_json: dict[str, object] | None = None,
) -> ReleasePlatformHealthComponentRead:
    return ReleasePlatformHealthComponentRead(
        component_code=component_code,
        title=title,
        health_status=health_status,
        summary=summary,
        details_json=details_json or {},
    )


def _import_run_health(runs: list[LunarFeedRun]) -> str:
    if not runs:
        return HEALTH_STATUS_DISABLED
    latest = runs[0]
    if latest.status == "FAILED":
        return HEALTH_STATUS_FAILED
    if latest.status in {"RUNNING", "PENDING"}:
        return HEALTH_STATUS_WARNING
    if any(run.status == "FAILED" for run in runs[:3]):
        return HEALTH_STATUS_WARNING
    return HEALTH_STATUS_HEALTHY


def get_release_feed_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    runs = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.id.desc())
        .limit(5)
    ).all()
    creds = get_credential_status()
    status = _import_run_health(runs)
    if not creds.credential_available and not runs:
        status = HEALTH_STATUS_DISABLED
    elif not creds.credential_available and runs:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="release_feed",
        title="Release Feed",
        health_status=status,
        summary=f"{len(runs)} recent Lunar feed runs; credentials configured={creds.credential_available}.",
        details_json={"run_status_counts": dict(Counter(run.status for run in runs))},
    )


def get_release_intelligence_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    issues = session.scalar(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
    ) or 0
    signals = session.scalar(
        select(func.count()).select_from(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)
    ) or 0
    status = HEALTH_STATUS_HEALTHY
    if issues == 0:
        status = HEALTH_STATUS_FAILED
    elif signals == 0:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="release_intelligence",
        title="Release Intelligence",
        health_status=status,
        summary=f"{issues} release issues and {signals} key signals tracked.",
        details_json={"issue_count": int(issues), "signal_count": int(signals)},
    )


def get_watchlists_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    watchlists = session.scalar(
        select(func.count()).select_from(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)
    ) or 0
    status = HEALTH_STATUS_HEALTHY if watchlists else HEALTH_STATUS_WARNING
    return _component(
        component_code="watchlists",
        title="Watchlists",
        health_status=status,
        summary=f"{watchlists} watchlists active for owner.",
        details_json={"watchlist_count": int(watchlists)},
    )


def get_spec_intelligence_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    recommendations = session.scalar(
        select(func.count())
        .select_from(SpecRecommendation)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ) or 0
    status = HEALTH_STATUS_HEALTHY if recommendations else HEALTH_STATUS_WARNING
    return _component(
        component_code="spec_intelligence",
        title="Spec Intelligence",
        health_status=status,
        summary=f"{recommendations} spec recommendations available.",
        details_json={"recommendation_count": int(recommendations)},
    )


def get_horizons_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    horizons = build_release_horizons(session, owner_user_id=owner_user_id)
    populated = (
        len(horizons.next_30_days)
        + len(horizons.next_60_days)
        + len(horizons.next_90_days)
        + len(horizons.announced)
    )
    status = HEALTH_STATUS_HEALTHY if populated else HEALTH_STATUS_WARNING
    return _component(
        component_code="horizons",
        title="Horizons",
        health_status=status,
        summary=f"Horizon windows contain {populated} scheduled or announced issues.",
        details_json={
            "next_30_days": len(horizons.next_30_days),
            "next_60_days": len(horizons.next_60_days),
            "next_90_days": len(horizons.next_90_days),
            "announced": len(horizons.announced),
        },
    )


def get_scheduler_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    config = session.exec(
        select(LunarScheduleConfig).where(LunarScheduleConfig.owner_user_id == owner_user_id)
    ).first()
    runs = session.exec(
        select(LunarScheduledRun)
        .where(LunarScheduledRun.owner_user_id == owner_user_id)
        .order_by(LunarScheduledRun.id.desc())
        .limit(5)
    ).all()
    status = HEALTH_STATUS_HEALTHY
    if config is None:
        status = HEALTH_STATUS_DISABLED
    elif not config.enabled:
        status = HEALTH_STATUS_WARNING
    elif runs and runs[0].status == "FAILED":
        status = HEALTH_STATUS_FAILED
    elif runs and any(run.status == "FAILED" for run in runs):
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="scheduler",
        title="Scheduler",
        health_status=status,
        summary=(
            f"Scheduler enabled={bool(config.enabled) if config else False}; "
            f"{len(runs)} recent scheduled runs."
        ),
        details_json={"run_status_counts": dict(Counter(run.status for run in runs))},
    )


def get_variants_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    variant_count = (
        len(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(issue_ids))).all()) if issue_ids else 0
    )
    status = HEALTH_STATUS_HEALTHY
    if issue_ids and variant_count == 0:
        status = HEALTH_STATUS_FAILED
    elif variant_count == 0:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="variants",
        title="Variants",
        health_status=status,
        summary=f"{variant_count} release variants indexed for owner catalog.",
        details_json={"variant_count": variant_count},
    )


def get_import_pipeline_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthComponentRead:
    runs = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.id.desc())
        .limit(10)
    ).all()
    status = _import_run_health(runs)
    completed = sum(1 for run in runs if run.status == "COMPLETED")
    failed = sum(1 for run in runs if run.status == "FAILED")
    if runs and failed > completed:
        status = HEALTH_STATUS_FAILED
    return _component(
        component_code="import_pipeline",
        title="Import Pipeline",
        health_status=status,
        summary=f"{len(runs)} recent import runs ({completed} completed, {failed} failed).",
        details_json={"run_status_counts": dict(Counter(run.status for run in runs))},
    )


def get_release_platform_health(session: Session, *, owner_user_id: int) -> ReleasePlatformHealthRead:
    components = [
        get_release_feed_health(session, owner_user_id=owner_user_id),
        get_release_intelligence_health(session, owner_user_id=owner_user_id),
        get_watchlists_health(session, owner_user_id=owner_user_id),
        get_spec_intelligence_health(session, owner_user_id=owner_user_id),
        get_horizons_health(session, owner_user_id=owner_user_id),
        get_scheduler_health(session, owner_user_id=owner_user_id),
        get_variants_health(session, owner_user_id=owner_user_id),
        get_import_pipeline_health(session, owner_user_id=owner_user_id),
    ]
    return ReleasePlatformHealthRead(
        overall_status=_aggregate_health([component.health_status for component in components]),
        components=components,
    )
