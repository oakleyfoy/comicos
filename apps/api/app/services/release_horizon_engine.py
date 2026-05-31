from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.release_intelligence import ReleaseIssueRead, ReleaseSeriesRead
from app.schemas.release_platform import ReleaseHorizonIssueRead, ReleaseHorizonsRead

HORIZON_ANNOUNCED = "ANNOUNCED"
HORIZON_NEXT_30 = "NEXT_30_DAYS"
HORIZON_NEXT_60 = "NEXT_60_DAYS"
HORIZON_NEXT_90 = "NEXT_90_DAYS"
HORIZON_FOC = "FOC_APPROACHING"
HORIZON_RELEASING = "RELEASING_SOON"
HORIZON_RELEASED = "RELEASED"


def _primary_horizon(issue: ReleaseIssue, *, today: date) -> str:
    release_date = issue.release_date
    foc_date = issue.foc_date
    if release_date is not None and release_date < today:
        return HORIZON_RELEASED
    if release_date is not None:
        days = (release_date - today).days
        if days <= 14:
            return HORIZON_RELEASING
        if days <= 30:
            return HORIZON_NEXT_30
        if days <= 60:
            return HORIZON_NEXT_60
        if days <= 90:
            return HORIZON_NEXT_90
    if foc_date is not None:
        foc_days = (foc_date - today).days
        if 0 <= foc_days <= 14:
            return HORIZON_FOC
    if issue.release_status.upper() == "ANNOUNCED" or release_date is None or (
        release_date is not None and (release_date - today).days > 90
    ):
        return HORIZON_ANNOUNCED
    return HORIZON_ANNOUNCED


def _in_window(release_date: date | None, *, today: date, max_days: int) -> bool:
    if release_date is None:
        return False
    delta = (release_date - today).days
    return 0 <= delta <= max_days


def build_release_horizons(session: Session, *, owner_user_id: int) -> ReleaseHorizonsRead:
    today = date.today()
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc().nulls_last(), ReleaseIssue.id.asc())
    ).all()

    buckets: dict[str, list[ReleaseHorizonIssueRead]] = {
        HORIZON_ANNOUNCED: [],
        HORIZON_NEXT_30: [],
        HORIZON_NEXT_60: [],
        HORIZON_NEXT_90: [],
        HORIZON_FOC: [],
        HORIZON_RELEASING: [],
        HORIZON_RELEASED: [],
    }

    for issue, series in rows:
        primary = _primary_horizon(issue, today=today)
        entry = ReleaseHorizonIssueRead(
            horizon=primary,
            issue=ReleaseIssueRead.model_validate(issue),
            series=ReleaseSeriesRead.model_validate(series),
        )
        buckets[primary].append(entry)
        if issue.foc_date is not None and 0 <= (issue.foc_date - today).days <= 14 and primary != HORIZON_RELEASED:
            if not any(row.issue.id == issue.id for row in buckets[HORIZON_FOC]):
                buckets[HORIZON_FOC].append(
                    ReleaseHorizonIssueRead(
                        horizon=HORIZON_FOC,
                        issue=ReleaseIssueRead.model_validate(issue),
                        series=ReleaseSeriesRead.model_validate(series),
                    )
                )
        if _in_window(issue.release_date, today=today, max_days=30) and primary not in (HORIZON_RELEASED,):
            if not any(row.issue.id == issue.id for row in buckets[HORIZON_NEXT_30]):
                buckets[HORIZON_NEXT_30].append(entry)
        if _in_window(issue.release_date, today=today, max_days=60):
            if not any(row.issue.id == issue.id for row in buckets[HORIZON_NEXT_60]):
                buckets[HORIZON_NEXT_60].append(entry)
        if _in_window(issue.release_date, today=today, max_days=90):
            if not any(row.issue.id == issue.id for row in buckets[HORIZON_NEXT_90]):
                buckets[HORIZON_NEXT_90].append(entry)

    return ReleaseHorizonsRead(
        announced=buckets[HORIZON_ANNOUNCED],
        next_30_days=buckets[HORIZON_NEXT_30],
        next_60_days=buckets[HORIZON_NEXT_60],
        next_90_days=buckets[HORIZON_NEXT_90],
        foc_approaching=buckets[HORIZON_FOC],
        releasing_soon=buckets[HORIZON_RELEASING],
        released=buckets[HORIZON_RELEASED],
    )


def list_issues_in_horizon_window(
    session: Session,
    *,
    owner_user_id: int,
    max_release_days: int,
) -> list[tuple[ReleaseIssue, ReleaseSeries]]:
    today = date.today()
    cutoff = today + timedelta(days=max_release_days)
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
    ).all()
    result: list[tuple[ReleaseIssue, ReleaseSeries]] = []
    for issue, series in rows:
        if issue.release_date is None:
            continue
        if issue.release_date < today:
            continue
        if issue.release_date <= cutoff:
            result.append((issue, series))
    return result
