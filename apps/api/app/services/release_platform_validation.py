from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, func, select

from app.models.lunar_feed import LunarFeedRun
from app.models.lunar_scheduler import LunarScheduleConfig, LunarScheduledRun
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.release_watchlist import CollectionContinuityAlert, ReleaseWatchlist
from app.models.spec_intelligence import SpecRecommendation
from app.schemas.release_platform_certification import ReleasePlatformValidationCheckRead, ReleasePlatformValidationRead
from app.services.continue_run_planning import build_continue_run_planning
from app.services.lunar_credentials import get_credential_status
from app.services.lunar_issue_identity import is_canonical_lunar_issue_uuid
from app.services.release_horizon_engine import build_release_horizons

PLATFORM_STATUS_PASS = "PASS"
PLATFORM_STATUS_WARNING = "WARNING"
PLATFORM_STATUS_FAIL = "FAIL"


def _aggregate_status(statuses: list[str]) -> str:
    if any(status == PLATFORM_STATUS_FAIL for status in statuses):
        return PLATFORM_STATUS_FAIL
    if any(status == PLATFORM_STATUS_WARNING for status in statuses):
        return PLATFORM_STATUS_WARNING
    return PLATFORM_STATUS_PASS


def _check(
    *,
    check_code: str,
    title: str,
    status: str,
    summary: str,
    details_json: dict[str, object],
) -> ReleasePlatformValidationCheckRead:
    return ReleasePlatformValidationCheckRead(
        check_code=check_code,
        title=title,
        status=status,
        summary=summary,
        details_json=details_json,
    )


def validate_release_intelligence(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    series_count = session.scalar(
        select(func.count()).select_from(ReleaseSeries).where(ReleaseSeries.owner_user_id == owner_user_id)
    ) or 0
    issue_count = session.scalar(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
    ) or 0
    signal_count = session.scalar(
        select(func.count()).select_from(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)
    ) or 0
    status = PLATFORM_STATUS_PASS
    if issue_count == 0 or series_count == 0:
        status = PLATFORM_STATUS_FAIL
    elif signal_count == 0:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="release_intelligence",
        title="Release Intelligence",
        status=status,
        summary=f"{series_count} series, {issue_count} issues, {signal_count} key signals indexed.",
        details_json={
            "series_count": int(series_count),
            "issue_count": int(issue_count),
            "signal_count": int(signal_count),
        },
    )


def validate_watchlists(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    watchlists = session.scalar(
        select(func.count()).select_from(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)
    ) or 0
    status = PLATFORM_STATUS_PASS if watchlists else PLATFORM_STATUS_WARNING
    return _check(
        check_code="watchlists",
        title="Watchlists",
        status=status,
        summary=f"{watchlists} release watchlists configured.",
        details_json={"watchlist_count": int(watchlists)},
    )


def validate_continuity(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    alerts = session.scalar(
        select(func.count())
        .select_from(CollectionContinuityAlert)
        .where(CollectionContinuityAlert.owner_user_id == owner_user_id)
    ) or 0
    plans = build_continue_run_planning(session, owner_user_id=owner_user_id)
    return _check(
        check_code="continuity",
        title="Continuity",
        status=PLATFORM_STATUS_PASS,
        summary=f"Continuity engine produced {len(plans)} advisory plans; {alerts} stored alerts.",
        details_json={"plan_count": len(plans), "alert_count": int(alerts)},
    )


def validate_horizons(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    horizons = build_release_horizons(session, owner_user_id=owner_user_id)
    populated = (
        len(horizons.next_30_days)
        + len(horizons.next_60_days)
        + len(horizons.next_90_days)
        + len(horizons.announced)
    )
    status = PLATFORM_STATUS_PASS if populated else PLATFORM_STATUS_WARNING
    return _check(
        check_code="horizons",
        title="Horizons",
        status=status,
        summary=(
            f"Horizon buckets populated: 30d={len(horizons.next_30_days)}, "
            f"60d={len(horizons.next_60_days)}, 90d={len(horizons.next_90_days)}."
        ),
        details_json={
            "next_30_days": len(horizons.next_30_days),
            "next_60_days": len(horizons.next_60_days),
            "next_90_days": len(horizons.next_90_days),
            "announced": len(horizons.announced),
        },
    )


def validate_spec_intelligence(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    recommendations = session.scalar(
        select(func.count())
        .select_from(SpecRecommendation)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ) or 0
    status = PLATFORM_STATUS_PASS if recommendations else PLATFORM_STATUS_WARNING
    return _check(
        check_code="spec_intelligence",
        title="Spec Intelligence",
        status=status,
        summary=f"{recommendations} spec recommendations generated for owner catalog.",
        details_json={"recommendation_count": int(recommendations)},
    )


def validate_lunar_connector(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    creds = get_credential_status()
    runs = session.scalar(
        select(func.count()).select_from(LunarFeedRun).where(LunarFeedRun.owner_user_id == owner_user_id)
    ) or 0
    completed = session.scalar(
        select(func.count())
        .select_from(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .where(LunarFeedRun.status == "COMPLETED")
    ) or 0
    status = PLATFORM_STATUS_PASS
    if runs == 0:
        status = PLATFORM_STATUS_WARNING
    elif completed == 0:
        status = PLATFORM_STATUS_FAIL
    elif not creds.credential_available:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="lunar_connector",
        title="Lunar Connector",
        status=status,
        summary=f"Credentials configured={creds.credential_available}; {completed}/{runs} completed import runs.",
        details_json={
            "credential_available": creds.credential_available,
            "import_run_count": int(runs),
            "completed_run_count": int(completed),
        },
    )


def validate_scheduler(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    config = session.exec(
        select(LunarScheduleConfig).where(LunarScheduleConfig.owner_user_id == owner_user_id)
    ).first()
    runs = session.scalar(
        select(func.count()).select_from(LunarScheduledRun).where(LunarScheduledRun.owner_user_id == owner_user_id)
    ) or 0
    status = PLATFORM_STATUS_PASS
    if config is None:
        status = PLATFORM_STATUS_WARNING
    elif not config.enabled:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="scheduler",
        title="Scheduler",
        status=status,
        summary=(
            f"Scheduler config={'present' if config else 'missing'}; "
            f"enabled={bool(config.enabled) if config else False}; runs={runs}."
        ),
        details_json={
            "config_present": config is not None,
            "enabled": bool(config.enabled) if config else False,
            "scheduled_run_count": int(runs),
        },
    )


def validate_variant_intelligence(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    variant_count = 0
    ratio_count = 0
    if issue_ids:
        variant_count = len(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(issue_ids))).all())
        ratio_count = len(
            session.exec(
                select(ReleaseVariant)
                .where(ReleaseVariant.issue_id.in_(issue_ids))
                .where(ReleaseVariant.is_incentive_variant.is_(True))
            ).all()
        )
    variant_signals = session.scalar(
        select(func.count())
        .select_from(ReleaseKeySignal)
        .where(ReleaseKeySignal.owner_user_id == owner_user_id)
        .where(ReleaseKeySignal.signal_type.in_(["VARIANT_RATIO", "HIGH_RATIO_VARIANT", "INCENTIVE_VARIANT"]))
    ) or 0
    status = PLATFORM_STATUS_PASS
    if issue_ids and variant_count == 0:
        status = PLATFORM_STATUS_FAIL
    elif variant_count == 0:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="variant_intelligence",
        title="Variant Intelligence",
        status=status,
        summary=f"{variant_count} variants ({ratio_count} incentive/ratio); {variant_signals} variant signals.",
        details_json={
            "variant_count": variant_count,
            "ratio_variant_count": ratio_count,
            "variant_signal_count": int(variant_signals),
        },
    )


def validate_reimport_idempotency(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationCheckRead:
    rows = session.exec(
        select(ReleaseIssue.series_id, ReleaseIssue.issue_number, ReleaseIssue.release_uuid).where(
            ReleaseIssue.owner_user_id == owner_user_id
        )
    ).all()
    canonical_groups: dict[tuple[int, str], set[str]] = defaultdict(set)
    for series_id, issue_number, release_uuid in rows:
        if is_canonical_lunar_issue_uuid(release_uuid):
            canonical_groups[(series_id, issue_number)].add(release_uuid)
    duplicate_canonical = sum(1 for uuids in canonical_groups.values() if len(uuids) > 1)

    recent_runs = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.id.desc())
        .limit(2)
    ).all()
    last_two_created = [run.records_created for run in recent_runs if run.records_created is not None]

    status = PLATFORM_STATUS_PASS
    if duplicate_canonical > 0:
        status = PLATFORM_STATUS_FAIL
    elif len(recent_runs) >= 2 and len(last_two_created) == 2 and last_two_created[0] > 0:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="reimport_idempotency",
        title="Re-import Idempotency",
        status=status,
        summary=(
            f"Duplicate canonical issue groups={duplicate_canonical}; "
            f"recent import created counts={last_two_created}."
        ),
        details_json={
            "duplicate_canonical_groups": duplicate_canonical,
            "recent_import_created_counts": last_two_created,
        },
    )


def validate_release_platform(session: Session, *, owner_user_id: int) -> ReleasePlatformValidationRead:
    checks = [
        validate_release_intelligence(session, owner_user_id=owner_user_id),
        validate_watchlists(session, owner_user_id=owner_user_id),
        validate_continuity(session, owner_user_id=owner_user_id),
        validate_horizons(session, owner_user_id=owner_user_id),
        validate_spec_intelligence(session, owner_user_id=owner_user_id),
        validate_lunar_connector(session, owner_user_id=owner_user_id),
        validate_scheduler(session, owner_user_id=owner_user_id),
        validate_variant_intelligence(session, owner_user_id=owner_user_id),
        validate_reimport_idempotency(session, owner_user_id=owner_user_id),
    ]
    overall = _aggregate_status([check.status for check in checks])
    return ReleasePlatformValidationRead(
        overall_status=overall,
        platform_certified=overall == PLATFORM_STATUS_PASS,
        checks=checks,
    )
