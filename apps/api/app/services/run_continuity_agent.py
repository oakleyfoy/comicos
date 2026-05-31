from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import ComicIssue, ComicTitle, InventoryCopy, OrderItem, Publisher, Variant
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.release_watchlist import CollectionContinuityAlert, CollectionRun
from app.schemas.release_watchlist import CollectionContinuityAlertRead, CollectionRunRead, WatchlistAgentExecutionRead
from app.services.release_watchlist_execution import AGENT_RUN_CONTINUITY, run_with_watchlist_execution


@dataclass
class OwnedIssueRow:
    publisher: str
    series_name: str
    issue_number: str


def _issue_value(value: str) -> float | None:
    cleaned = value.strip().replace("#", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _inventory_issue_rows(session: Session, *, owner_user_id: int) -> list[OwnedIssueRow]:
    rows = session.exec(
        select(Publisher.name, ComicTitle.name, ComicIssue.issue_number)
        .select_from(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.user_id == owner_user_id)
        .order_by(Publisher.name.asc(), ComicTitle.name.asc(), ComicIssue.issue_number.asc())
    ).all()
    return [OwnedIssueRow(publisher=str(row[0]), series_name=str(row[1]), issue_number=str(row[2])) for row in rows]


def detect_owned_runs(session: Session, *, owner_user_id: int) -> list[CollectionRun]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for row in _inventory_issue_rows(session, owner_user_id=owner_user_id):
        grouped.setdefault((row.publisher, row.series_name), []).append(row.issue_number)
    created: list[CollectionRun] = []
    for (publisher, series_name), issue_numbers in grouped.items():
        numerics = sorted(v for v in (_issue_value(issue) for issue in issue_numbers) if v is not None)
        unique_count = len(set(issue_numbers))
        first_issue = issue_numbers[0]
        latest_issue = issue_numbers[-1]
        if numerics:
            first_issue = str(int(numerics[0]) if numerics[0].is_integer() else numerics[0])
            latest_issue = str(int(numerics[-1]) if numerics[-1].is_integer() else numerics[-1])
        status = "ACTIVE_RUN" if unique_count > 1 else "SINGLE_ISSUE"
        row = CollectionRun(
            owner_user_id=owner_user_id,
            publisher=publisher,
            series_name=series_name,
            first_issue_owned=first_issue,
            latest_issue_owned=latest_issue,
            issue_count_owned=unique_count,
            continuity_status=status,
        )
        session.add(row)
        created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def compare_runs_to_upcoming_releases(session: Session, *, owner_user_id: int, runs: list[CollectionRun]) -> list[tuple[CollectionRun, ReleaseIssue, ReleaseSeries]]:
    by_series = {(run.publisher.lower(), run.series_name.lower()): run for run in runs}
    issues = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
    ).all()
    matches: list[tuple[CollectionRun, ReleaseIssue, ReleaseSeries]] = []
    for issue, series in issues:
        run = by_series.get((series.publisher.lower(), series.series_name.lower()))
        if run is not None:
            matches.append((run, issue, series))
    return matches


def matched_release_issues_for_inventory(session: Session, *, owner_user_id: int) -> list[tuple[ReleaseIssue, ReleaseSeries]]:
    owned_pairs = {
        (row.publisher.lower(), row.series_name.lower())
        for row in _inventory_issue_rows(session, owner_user_id=owner_user_id)
    }
    issues = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
    ).all()
    return [
        (issue, series)
        for issue, series in issues
        if (series.publisher.lower(), series.series_name.lower()) in owned_pairs
    ]


def detect_next_issue_available(
    session: Session,
    *,
    owner_user_id: int,
    matches: list[tuple[CollectionRun, ReleaseIssue, ReleaseSeries]],
) -> list[CollectionContinuityAlert]:
    created: list[CollectionContinuityAlert] = []
    for run, issue, series in matches:
        latest = _issue_value(run.latest_issue_owned)
        issue_value = _issue_value(issue.issue_number)
        if latest is None or issue_value is None or issue_value != latest + 1:
            continue
        for alert_type in ("CONTINUE_RUN", "NEXT_ISSUE_ANNOUNCED"):
            row = CollectionContinuityAlert(
                owner_user_id=owner_user_id,
                release_issue_id=int(issue.id or 0),
                alert_type=alert_type,
                alert_status="OPEN",
                alert_payload_json={
                    "publisher": series.publisher,
                    "series_name": series.series_name,
                    "latest_issue_owned": run.latest_issue_owned,
                    "upcoming_issue_number": issue.issue_number,
                },
            )
            session.add(row)
            created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def detect_missing_issue_risk(
    session: Session,
    *,
    owner_user_id: int,
    matches: list[tuple[CollectionRun, ReleaseIssue, ReleaseSeries]],
) -> list[CollectionContinuityAlert]:
    created: list[CollectionContinuityAlert] = []
    for run, issue, series in matches:
        latest = _issue_value(run.latest_issue_owned)
        issue_value = _issue_value(issue.issue_number)
        if latest is None or issue_value is None or issue_value <= latest + 1:
            continue
        row = CollectionContinuityAlert(
            owner_user_id=owner_user_id,
            release_issue_id=int(issue.id or 0),
            alert_type="MISSING_ISSUE_RISK",
            alert_status="OPEN",
            alert_payload_json={
                "publisher": series.publisher,
                "series_name": series.series_name,
                "latest_issue_owned": run.latest_issue_owned,
                "upcoming_issue_number": issue.issue_number,
                "gap_size": issue_value - latest - 1,
            },
        )
        session.add(row)
        created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def run_continuity_detection(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[CollectionRunRead], list[CollectionContinuityAlertRead], WatchlistAgentExecutionRead]:
    def runner():
        runs = detect_owned_runs(session, owner_user_id=owner_user_id)
        matches = compare_runs_to_upcoming_releases(session, owner_user_id=owner_user_id, runs=runs)
        alerts = []
        alerts.extend(detect_next_issue_available(session, owner_user_id=owner_user_id, matches=matches))
        alerts.extend(detect_missing_issue_risk(session, owner_user_id=owner_user_id, matches=matches))
        return (
            [CollectionRunRead.model_validate(row) for row in runs],
            [CollectionContinuityAlertRead.model_validate(row) for row in alerts],
        )

    result, execution = run_with_watchlist_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_RUN_CONTINUITY,
        runner=runner,
    )
    runs, alerts = result
    return runs, alerts, WatchlistAgentExecutionRead.model_validate(execution)


def list_runs_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(CollectionRun)
        .where(CollectionRun.owner_user_id == owner_user_id)
        .order_by(CollectionRun.created_at.desc(), CollectionRun.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [CollectionRunRead.model_validate(row) for row in page], len(rows)


def list_alerts_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(CollectionContinuityAlert)
        .where(CollectionContinuityAlert.owner_user_id == owner_user_id)
        .order_by(CollectionContinuityAlert.created_at.desc(), CollectionContinuityAlert.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [CollectionContinuityAlertRead.model_validate(row) for row in page], len(rows)
