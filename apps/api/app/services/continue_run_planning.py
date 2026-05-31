from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.schemas.release_intelligence import ReleaseIssueRead, ReleaseSeriesRead
from app.schemas.release_platform import ContinueRunPlanRead
from app.services.opportunity_scoring import compute_opportunity_ranking_score, is_strong_new_opportunity
from app.services.run_continuity_agent import _inventory_issue_rows, _issue_value

MILESTONE_NUMBERS = {25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 250.0, 300.0, 500.0, 1000.0}


@dataclass
class _OwnedRunSnapshot:
    publisher: str
    series_name: str
    first_issue_owned: str
    latest_issue_owned: str
    issue_count_owned: int
    owned_values: set[float]


def _owned_runs_snapshot(session: Session, *, owner_user_id: int) -> list[_OwnedRunSnapshot]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for row in _inventory_issue_rows(session, owner_user_id=owner_user_id):
        grouped.setdefault((row.publisher, row.series_name), []).append(row.issue_number)
    runs: list[_OwnedRunSnapshot] = []
    for (publisher, series_name), issue_numbers in grouped.items():
        numerics = sorted(v for v in (_issue_value(issue) for issue in issue_numbers) if v is not None)
        unique_count = len(set(issue_numbers))
        first_issue = issue_numbers[0]
        latest_issue = issue_numbers[-1]
        owned_values = set(numerics)
        if numerics:
            first_issue = str(int(numerics[0]) if numerics[0].is_integer() else numerics[0])
            latest_issue = str(int(numerics[-1]) if numerics[-1].is_integer() else numerics[-1])
        runs.append(
            _OwnedRunSnapshot(
                publisher=publisher,
                series_name=series_name,
                first_issue_owned=first_issue,
                latest_issue_owned=latest_issue,
                issue_count_owned=unique_count,
                owned_values=owned_values,
            )
        )
    return runs


def _plan_entry(
    *,
    plan_type: str,
    series: ReleaseSeries,
    issue: ReleaseIssue,
    run: _OwnedRunSnapshot | None,
) -> ContinueRunPlanRead:
    return ContinueRunPlanRead(
        plan_type=plan_type,
        publisher=series.publisher,
        series_name=series.series_name,
        latest_issue_owned=run.latest_issue_owned if run else None,
        target_issue_number=issue.issue_number,
        release_issue_id=int(issue.id or 0),
        issue=ReleaseIssueRead.model_validate(issue),
        series=ReleaseSeriesRead.model_validate(series),
    )


def _signals_for_issues(session: Session, *, owner_user_id: int) -> dict[int, set[str]]:
    signals_by_issue: dict[int, set[str]] = {}
    for signal in session.exec(
        select(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)
    ).all():
        signals_by_issue.setdefault(signal.issue_id, set()).add(signal.signal_type)
    return signals_by_issue


def build_continue_run_planning(session: Session, *, owner_user_id: int) -> list[ContinueRunPlanRead]:
    runs = _owned_runs_snapshot(session, owner_user_id=owner_user_id)
    by_series = {(run.publisher.lower(), run.series_name.lower()): run for run in runs}
    owned_series = set(by_series.keys())
    signals_by_issue = _signals_for_issues(session, owner_user_id=owner_user_id)
    issues = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
    ).all()

    plans: list[ContinueRunPlanRead] = []
    for issue, series in issues:
        key = (series.publisher.lower(), series.series_name.lower())
        run = by_series.get(key)
        issue_value = _issue_value(issue.issue_number)
        issue_signals = signals_by_issue.get(int(issue.id or 0), set())
        ranking_score, _ = compute_opportunity_ranking_score(
            session,
            owner_user_id=owner_user_id,
            issue=issue,
            series=series,
            signal_types=issue_signals,
        )

        if run is not None and issue_value is not None:
            latest = _issue_value(run.latest_issue_owned)
            if (
                latest is not None
                and issue_value in MILESTONE_NUMBERS
                and issue_value > latest
                and latest >= issue_value - 3
            ):
                plans.append(_plan_entry(plan_type="COMPLETE_RUN", series=series, issue=issue, run=run))
                continue
            if latest is not None and issue_value == latest + 1:
                if run.issue_count_owned >= 2:
                    plans.append(_plan_entry(plan_type="CONTINUE_RUN", series=series, issue=issue, run=run))
                else:
                    plans.append(_plan_entry(plan_type="START_FOLLOWING", series=series, issue=issue, run=run))
                continue
            if latest is not None and issue_value > latest + 1:
                plans.append(_plan_entry(plan_type="WATCH", series=series, issue=issue, run=run))
                continue
            if (
                latest is not None
                and issue_value in MILESTONE_NUMBERS
                and issue_value > latest
                and latest >= issue_value - 3
            ):
                plans.append(_plan_entry(plan_type="COMPLETE_RUN", series=series, issue=issue, run=run))
                continue

        if key not in owned_series:
            if is_strong_new_opportunity(issue_signals, ranking_score):
                plans.append(_plan_entry(plan_type="NEW_OPPORTUNITY", series=series, issue=issue, run=None))
            elif ranking_score >= 30 or issue_signals:
                plans.append(_plan_entry(plan_type="WATCH", series=series, issue=issue, run=None))
            elif issue.issue_number.strip().replace("#", "") == "1":
                plans.append(_plan_entry(plan_type="PASS", series=series, issue=issue, run=None))
            continue

        if run is not None and issue_value is not None and issue_value in MILESTONE_NUMBERS:
            latest = _issue_value(run.latest_issue_owned)
            if latest is not None and latest < issue_value and latest >= issue_value - 3:
                plans.append(_plan_entry(plan_type="COMPLETE_RUN", series=series, issue=issue, run=run))

    return plans
