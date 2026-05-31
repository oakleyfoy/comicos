from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.lunar_feed import LunarFeedRun, LunarFocAlert
from app.models.lunar_scheduler import LunarScheduleConfig, LunarScheduledRun
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.release_watchlist import ReleaseWatchlist
from app.schemas.release_platform_certification import (
    ReleasePlatformImportSummaryRead,
    ReleasePlatformSchedulerSummaryRead,
    ReleasePlatformSummaryRead,
)
from app.services.opportunity_intelligence import build_opportunity_intelligence
from app.services.production_certification import calculate_readiness_score
from app.services.release_platform_validation import validate_release_platform


def _import_summary(session: Session, *, owner_user_id: int) -> ReleasePlatformImportSummaryRead:
    runs = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.id.desc())
    ).all()
    last = runs[0] if runs else None
    last_success = next((run for run in runs if run.status == "COMPLETED"), None)
    last_failed = next((run for run in runs if run.status == "FAILED"), None)
    return ReleasePlatformImportSummaryRead(
        last_import_at=last.completed_at or last.started_at if last else None,
        last_successful_import_at=last_success.completed_at or last_success.started_at if last_success else None,
        last_failed_import_at=last_failed.completed_at or last_failed.started_at if last_failed else None,
        last_import_status=last.status if last else None,
        last_import_records_processed=int(last.records_processed) if last else 0,
        total_import_runs=len(runs),
    )


def _scheduler_summary(session: Session, *, owner_user_id: int) -> ReleasePlatformSchedulerSummaryRead:
    config = session.exec(
        select(LunarScheduleConfig).where(LunarScheduleConfig.owner_user_id == owner_user_id)
    ).first()
    last_run = session.exec(
        select(LunarScheduledRun)
        .where(LunarScheduledRun.owner_user_id == owner_user_id)
        .order_by(LunarScheduledRun.id.desc())
    ).first()
    return ReleasePlatformSchedulerSummaryRead(
        scheduler_enabled=bool(config.enabled) if config else False,
        schedule_time_utc=config.schedule_time if config else None,
        last_scheduled_run_status=last_run.status if last_run else None,
        last_scheduled_run_at=last_run.completed_at or last_run.started_at if last_run else None,
    )


def _total_opportunities(session: Session, *, owner_user_id: int) -> int:
    opportunities = build_opportunity_intelligence(session, owner_user_id=owner_user_id)
    issue_ids: set[int] = set()
    for bucket in (
        opportunities.top_new_opportunities,
        opportunities.top_spec_opportunities,
        opportunities.top_variant_opportunities,
        opportunities.top_first_appearances,
        opportunities.top_milestone_books,
        opportunities.top_new_number_ones,
    ):
        for row in bucket:
            issue_ids.add(row.release_issue_id)
    return len(issue_ids)


def get_release_platform_summary(session: Session, *, owner_user_id: int) -> ReleasePlatformSummaryRead:
    validation = validate_release_platform(session, owner_user_id=owner_user_id)
    readiness = calculate_readiness_score([check.status for check in validation.checks])

    total_releases = session.scalar(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
    ) or 0
    total_series = session.scalar(
        select(func.count()).select_from(ReleaseSeries).where(ReleaseSeries.owner_user_id == owner_user_id)
    ) or 0
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    total_variants = (
        len(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(issue_ids))).all()) if issue_ids else 0
    )
    total_new_number_ones = session.scalar(
        select(func.count())
        .select_from(ReleaseKeySignal)
        .where(ReleaseKeySignal.owner_user_id == owner_user_id)
        .where(ReleaseKeySignal.signal_type == "NEW_NUMBER_ONE")
    ) or 0
    total_watchlists = session.scalar(
        select(func.count()).select_from(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)
    ) or 0
    total_foc_alerts = session.scalar(
        select(func.count()).select_from(LunarFocAlert).where(LunarFocAlert.owner_user_id == owner_user_id)
    ) or 0

    return ReleasePlatformSummaryRead(
        total_releases=int(total_releases),
        total_series=int(total_series),
        total_variants=total_variants,
        total_new_number_ones=int(total_new_number_ones),
        total_opportunities=_total_opportunities(session, owner_user_id=owner_user_id),
        total_watchlists=int(total_watchlists),
        total_foc_alerts=int(total_foc_alerts),
        scheduler=_scheduler_summary(session, owner_user_id=owner_user_id),
        import_summary=_import_summary(session, owner_user_id=owner_user_id),
        platform_readiness_score=readiness,
    )
