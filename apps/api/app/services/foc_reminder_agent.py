from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.models.release_watchlist import ReleaseReminder
from app.schemas.release_watchlist import ReleaseReminderRead, WatchlistAgentExecutionRead
from app.services.release_watchlist_execution import AGENT_FOC_REMINDERS, run_with_watchlist_execution
from app.services.release_watchlists import list_watchlist_matches
from app.services.run_continuity_agent import matched_release_issues_for_inventory


def detect_foc_deadlines(session: Session, *, owner_user_id: int) -> list[tuple[int, date, str]]:
    today = date.today()
    matched_ids = {issue.id: issue for issue, _series in matched_release_issues_for_inventory(session, owner_user_id=owner_user_id)}
    for match in list_watchlist_matches(session, owner_user_id=owner_user_id, limit=500):
        matched_ids[match.release_issue.id] = match.release_issue
    items: list[tuple[int, date, str]] = []
    for issue in matched_ids.values():
        if issue.foc_date is None:
            continue
        delta = (issue.foc_date - today).days
        if delta < 0:
            reminder_type = "FOC_MISSED"
        elif delta == 0:
            reminder_type = "FOC_TODAY"
        elif delta <= 7:
            reminder_type = "FOC_APPROACHING"
        else:
            continue
        items.append((issue.id, issue.foc_date, reminder_type))
    return items


def generate_foc_reminders(session: Session, *, owner_user_id: int) -> list[ReleaseReminder]:
    created: list[ReleaseReminder] = []
    for issue_id, reminder_date, reminder_type in detect_foc_deadlines(session, owner_user_id=owner_user_id):
        row = ReleaseReminder(
            owner_user_id=owner_user_id,
            release_issue_id=issue_id,
            reminder_type=reminder_type,
            reminder_date=reminder_date,
            reminder_status="OPEN",
        )
        session.add(row)
        created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def run_foc_reminders(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[ReleaseReminderRead], WatchlistAgentExecutionRead]:
    def runner():
        reminders = generate_foc_reminders(session, owner_user_id=owner_user_id)
        return [ReleaseReminderRead.model_validate(row) for row in reminders]

    result, execution = run_with_watchlist_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_FOC_REMINDERS,
        runner=runner,
    )
    return result, WatchlistAgentExecutionRead.model_validate(execution)
