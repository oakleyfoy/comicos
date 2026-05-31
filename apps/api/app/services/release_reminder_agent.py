from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.release_watchlist import ReleaseReminder
from app.schemas.release_watchlist import ReleaseReminderRead, WatchlistAgentExecutionRead
from app.services.release_watchlist_execution import AGENT_RELEASE_REMINDERS, run_with_watchlist_execution
from app.services.release_watchlists import list_watchlist_matches
from app.services.run_continuity_agent import matched_release_issues_for_inventory


def detect_upcoming_releases(session: Session, *, owner_user_id: int) -> list[tuple[int, date, str]]:
    today = date.today()
    matched_ids = {issue.id: issue for issue, _series in matched_release_issues_for_inventory(session, owner_user_id=owner_user_id)}
    for match in list_watchlist_matches(session, owner_user_id=owner_user_id, limit=500):
        matched_ids[match.release_issue.id] = match.release_issue
    items: list[tuple[int, date, str]] = []
    for issue in matched_ids.values():
        if issue.release_date is None:
            continue
        delta = (issue.release_date - today).days
        if delta == 0:
            reminder_type = "RELEASE_TODAY"
        elif delta == 1:
            reminder_type = "RELEASE_TOMORROW"
        elif 0 <= delta <= 7:
            reminder_type = "RELEASE_THIS_WEEK"
        else:
            continue
        items.append((issue.id, issue.release_date, reminder_type))
    return items


def generate_release_reminders(session: Session, *, owner_user_id: int) -> list[ReleaseReminder]:
    created: list[ReleaseReminder] = []
    for issue_id, reminder_date, reminder_type in detect_upcoming_releases(session, owner_user_id=owner_user_id):
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


def run_release_reminders(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[ReleaseReminderRead], WatchlistAgentExecutionRead]:
    def runner():
        reminders = generate_release_reminders(session, owner_user_id=owner_user_id)
        return [ReleaseReminderRead.model_validate(row) for row in reminders]

    result, execution = run_with_watchlist_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_RELEASE_REMINDERS,
        runner=runner,
    )
    return result, WatchlistAgentExecutionRead.model_validate(execution)


def list_reminders_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ReleaseReminder)
        .where(ReleaseReminder.owner_user_id == owner_user_id)
        .order_by(ReleaseReminder.reminder_date.asc(), ReleaseReminder.created_at.desc(), ReleaseReminder.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [ReleaseReminderRead.model_validate(row) for row in page], len(rows)
