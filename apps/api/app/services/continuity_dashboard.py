from __future__ import annotations

from sqlmodel import Session

from app.models.release_intelligence import ReleaseIssue
from app.schemas.release_intelligence import ReleaseIssueRead
from app.schemas.release_watchlist import ContinuityDashboardRead, WatchlistAgentExecutionRead
from app.services.release_reminder_agent import list_reminders_for_owner
from app.services.release_watchlist_execution import list_executions_for_owner
from app.services.release_watchlists import list_watchlist_matches, list_watchlists
from app.services.run_continuity_agent import list_alerts_for_owner, list_runs_for_owner


def build_continuity_dashboard(session: Session, *, owner_user_id: int) -> ContinuityDashboardRead:
    runs, _ = list_runs_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    alerts, _ = list_alerts_for_owner(session, owner_user_id=owner_user_id, limit=50, offset=0)
    reminders, _ = list_reminders_for_owner(session, owner_user_id=owner_user_id, limit=100, offset=0)
    watchlists, _ = list_watchlists(session, owner_user_id=owner_user_id, limit=20, offset=0)
    matches = list_watchlist_matches(session, owner_user_id=owner_user_id, limit=50)
    executions, _ = list_executions_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)

    foc_reminders = [row for row in reminders if row.reminder_type.startswith("FOC_")]
    release_reminders = [row for row in reminders if row.reminder_type.startswith("RELEASE_")]
    unique_upcoming: dict[int, ReleaseIssueRead] = {}
    for match in matches:
        issue = session.get(ReleaseIssue, match.release_issue.id)
        if issue is not None:
            unique_upcoming[int(issue.id or 0)] = ReleaseIssueRead.model_validate(issue)

    return ContinuityDashboardRead(
        active_runs=runs,
        continuity_alerts=alerts,
        foc_reminders=foc_reminders[:20],
        release_reminders=release_reminders[:20],
        watchlists=watchlists,
        watchlist_matches=matches,
        upcoming_watched_releases=list(unique_upcoming.values())[:20],
        agent_activity=[WatchlistAgentExecutionRead.model_validate(row) for row in executions],
    )
