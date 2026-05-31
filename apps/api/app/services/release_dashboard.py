from __future__ import annotations

from sqlmodel import Session

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.release_intelligence import (
    ReleaseAgentExecutionRead,
    ReleaseIntelligenceDashboardRead,
    ReleaseIssueRead,
    ReleaseSeriesRead,
    ReleaseSignalFeedItemRead,
)
from app.services.release_import import list_issues_for_owner, list_signals_for_owner
from app.services.release_intelligence import list_executions_for_owner
from app.services.release_variant_metrics import (
    count_cover_variants_for_owner,
    count_ratio_variants_for_owner,
    count_variants_for_owner,
    list_recent_variants,
    list_top_ratio_variants,
)


def _build_signal_feed(session: Session, *, owner_user_id: int, signal_type: str, limit: int = 10) -> list[ReleaseSignalFeedItemRead]:
    signal_rows, _ = list_signals_for_owner(
        session,
        owner_user_id=owner_user_id,
        signal_type=signal_type,
        limit=limit,
        offset=0,
    )
    items: list[ReleaseSignalFeedItemRead] = []
    for signal in signal_rows:
        issue = session.get(ReleaseIssue, signal.issue_id)
        if issue is None:
            continue
        series = session.get(ReleaseSeries, issue.series_id)
        if series is None:
            continue
        items.append(
            ReleaseSignalFeedItemRead(
                series=ReleaseSeriesRead.model_validate(series),
                issue=ReleaseIssueRead.model_validate(issue),
                signal=signal,
            )
        )
    return items


def build_release_dashboard(session: Session, *, owner_user_id: int) -> ReleaseIntelligenceDashboardRead:
    issues, _ = list_issues_for_owner(session, owner_user_id=owner_user_id, limit=100, offset=0)
    upcoming = [issue for issue in issues if issue.release_date is not None][:10]
    foc_calendar = [issue for issue in issues if issue.foc_date is not None][:10]
    executions, _ = list_executions_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    return ReleaseIntelligenceDashboardRead(
        upcoming_releases=upcoming,
        foc_calendar=foc_calendar,
        new_number_one_feed=_build_signal_feed(session, owner_user_id=owner_user_id, signal_type="NEW_NUMBER_ONE"),
        key_issue_feed=[
            item
            for signal_type in (
                "FIRST_APPEARANCE",
                "ORIGIN_ISSUE",
                "ANNIVERSARY_ISSUE",
                "MILESTONE_NUMBERING",
                "DEATH_ISSUE",
                "STATUS_QUO_CHANGE",
            )
            for item in _build_signal_feed(session, owner_user_id=owner_user_id, signal_type=signal_type, limit=5)
        ][:10],
        variant_feed=[
            item
            for signal_type in ("VARIANT_RATIO", "INCENTIVE_VARIANT", "HIGH_RATIO_VARIANT", "OPEN_ORDER_VARIANT")
            for item in _build_signal_feed(session, owner_user_id=owner_user_id, signal_type=signal_type, limit=5)
        ][:10],
        agent_activity=[ReleaseAgentExecutionRead.model_validate(row) for row in executions],
        variant_count=count_variants_for_owner(session, owner_user_id=owner_user_id),
        ratio_variant_count=count_ratio_variants_for_owner(session, owner_user_id=owner_user_id),
        cover_variant_count=count_cover_variants_for_owner(session, owner_user_id=owner_user_id),
        recent_variants=list_recent_variants(session, owner_user_id=owner_user_id, limit=10),
        top_ratio_variants=list_top_ratio_variants(session, owner_user_id=owner_user_id, limit=10),
    )
