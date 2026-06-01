from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session

from app.schemas.future_release_dashboard import FutureReleaseDashboardRead, FutureReleaseDashboardSummaryRead
from app.schemas.release_intelligence import ReleaseIssueRead
from app.services.collected_runs import latest_collected_run_rows, persist_collected_runs
from app.services.future_release_actions import latest_future_release_action_rows, persist_future_release_actions
from app.services.future_release_matches import latest_future_release_match_rows, persist_future_release_matches
from app.services.next_issues import latest_next_issue_rows, persist_next_issues
from app.services.release_watchlists import list_watchlist_matches

SECTION_LIMIT = 25


def _ensure_pipeline(session: Session, *, owner_user_id: int) -> None:
    persist_collected_runs(session, owner_user_id=owner_user_id)
    persist_next_issues(session, owner_user_id=owner_user_id)
    persist_future_release_matches(session, owner_user_id=owner_user_id)
    persist_future_release_actions(session, owner_user_id=owner_user_id)


def _issue_is_upcoming(issue: ReleaseIssueRead, *, today: date) -> bool:
    if issue.release_date is not None and issue.release_date > today:
        return True
    if issue.foc_date is not None and issue.foc_date >= today:
        return True
    return False


def _foc_in_week(foc: date | None, *, today: date) -> bool:
    if foc is None:
        return False
    week_end = today + timedelta(days=7)
    return today <= foc <= week_end


def build_future_release_dashboard_summary(
    session: Session,
    *,
    owner_user_id: int,
    refresh: bool = False,
) -> FutureReleaseDashboardSummaryRead:
    if refresh:
        _ensure_pipeline(session, owner_user_id=owner_user_id)

    today = date.today()
    runs = latest_collected_run_rows(session, owner_user_id=owner_user_id)
    active_runs = sum(1 for row in runs.values() if row.run_status == "ACTIVE")

    matches = list(latest_future_release_match_rows(session, owner_user_id=owner_user_id).values())
    upcoming_issues = len(matches)

    foc_this_week = sum(1 for row in matches if _foc_in_week(row.foc_date, today=today))

    actions = list(latest_future_release_action_rows(session, owner_user_id=owner_user_id).values())
    preorder_now = sum(1 for row in actions if row.action_type == "PREORDER_NOW")
    missed_foc = sum(1 for row in actions if row.action_type == "MISSED_FOC")

    return FutureReleaseDashboardSummaryRead(
        active_runs=active_runs,
        upcoming_issues=upcoming_issues,
        foc_this_week=foc_this_week,
        preorder_now=preorder_now,
        missed_foc=missed_foc,
    )


def build_future_release_dashboard(
    session: Session,
    *,
    owner_user_id: int,
) -> FutureReleaseDashboardRead:
    _ensure_pipeline(session, owner_user_id=owner_user_id)
    today = date.today()

    summary = build_future_release_dashboard_summary(session, owner_user_id=owner_user_id, refresh=False)

    from app.services.next_issues import list_next_issues

    next_items, _ = list_next_issues(session, owner_user_id=owner_user_id, limit=SECTION_LIMIT, offset=0)

    from app.services.future_release_matches import list_future_release_matches

    match_items, _ = list_future_release_matches(session, owner_user_id=owner_user_id, limit=200, offset=0)
    upcoming_foc = sorted(
        [row for row in match_items if row.foc_date is not None],
        key=lambda row: row.foc_date or "",
    )[:SECTION_LIMIT]

    from app.services.future_release_actions import list_future_release_actions

    action_items, _ = list_future_release_actions(session, owner_user_id=owner_user_id, limit=200, offset=0)
    preorder_now = [row for row in action_items if row.action_type == "PREORDER_NOW"][:SECTION_LIMIT]
    this_week = [row for row in action_items if row.action_type == "PREORDER_THIS_WEEK"][:SECTION_LIMIT]
    missed_foc = [row for row in action_items if row.action_type == "MISSED_FOC"][:SECTION_LIMIT]

    watchlist_all = list_watchlist_matches(session, owner_user_id=owner_user_id, limit=100)
    watchlist = [
        match
        for match in watchlist_all
        if _issue_is_upcoming(match.release_issue, today=today)
    ][:SECTION_LIMIT]

    return FutureReleaseDashboardRead(
        summary=summary,
        next_issues=next_items,
        upcoming_foc=upcoming_foc,
        preorder_now=preorder_now,
        this_week=this_week,
        missed_foc=missed_foc,
        watchlist=watchlist,
    )
