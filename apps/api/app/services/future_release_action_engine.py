from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.models.future_release_action import FUTURE_RELEASE_ACTION_TYPES
from app.models.future_release_match import FutureReleaseMatch

PREORDER_NOW_MAX_DAYS = 3
PREORDER_THIS_WEEK_MAX_DAYS = 10


@dataclass(frozen=True)
class FutureReleaseActionCandidate:
    series_name: str
    issue_number: str
    action_type: str
    priority_score: float
    foc_date: date | None
    release_id: int | None


def _days_until_foc(*, foc_date: date | None, today: date) -> int | None:
    if foc_date is None:
        return None
    return (foc_date - today).days


def determine_action_type(*, foc_date: date | None, today: date) -> str:
    days = _days_until_foc(foc_date=foc_date, today=today)
    if days is None:
        return "WATCH"
    if days < 0:
        return "MISSED_FOC"
    if days <= PREORDER_NOW_MAX_DAYS:
        return "PREORDER_NOW"
    if days <= PREORDER_THIS_WEEK_MAX_DAYS:
        return "PREORDER_THIS_WEEK"
    return "WATCH"


def score_action_priority(*, action_type: str, foc_date: date | None, today: date) -> float:
    days = _days_until_foc(foc_date=foc_date, today=today)
    if action_type == "MISSED_FOC":
        return 92.0
    if days is None:
        return 55.0
    if days <= PREORDER_NOW_MAX_DAYS:
        return min(100.0, max(95.0, 98.0 - float(days)))
    if days <= 7:
        return min(94.0, max(85.0, 92.0 - float(days)))
    if action_type == "PREORDER_THIS_WEEK":
        return max(80.0, 88.0 - float(days) * 0.5)
    return max(50.0, 70.0 - float(days) * 0.25)


def _match_from_row(row: FutureReleaseMatch) -> FutureReleaseActionCandidate:
    today = date.today()
    action_type = determine_action_type(foc_date=row.foc_date, today=today)
    if action_type not in FUTURE_RELEASE_ACTION_TYPES:
        action_type = "WATCH"
    priority = score_action_priority(action_type=action_type, foc_date=row.foc_date, today=today)
    return FutureReleaseActionCandidate(
        series_name=row.series_name,
        issue_number=row.issue_number,
        action_type=action_type,
        priority_score=round(priority, 1),
        foc_date=row.foc_date,
        release_id=int(row.release_id),
    )


def generate_future_release_actions(
    matches: list[FutureReleaseMatch],
) -> list[FutureReleaseActionCandidate]:
    candidates = [_match_from_row(row) for row in matches]
    candidates.sort(key=lambda item: (-item.priority_score, item.series_name.lower(), item.issue_number))
    return candidates
