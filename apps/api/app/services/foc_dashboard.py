from __future__ import annotations

import json
from datetime import date

from sqlmodel import Session, select

from app.models.pull_list import PullList, PullListDecision, PullListIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.foc_dashboard import (
    FocDashboardItemRead,
    FocDashboardListResponse,
    FocDashboardRead,
    FocDashboardSection,
    FocDashboardSummaryRead,
)
from app.services.foc_dates import days_until_foc, days_until_release, foc_status_bucket, utc_today

_SECTION_ACTION_REQUIRED: FocDashboardSection = "ACTION_REQUIRED"
_SECTION_UPCOMING_FOC: FocDashboardSection = "UPCOMING_FOC"
_SECTION_UPCOMING_RELEASES: FocDashboardSection = "UPCOMING_RELEASES"
_SECTION_MISSED_FOC: FocDashboardSection = "MISSED_FOC"
_SECTION_WATCHLIST: FocDashboardSection = "WATCHLIST"


def _reasons_from_explanation(explanation: str) -> list[str]:
    if not explanation:
        return []
    try:
        parsed = json.loads(explanation)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        pass
    return [explanation]


def _latest_decision_rows(session: Session, *, owner_user_id: int) -> dict[int, PullListDecision]:
    rows = session.exec(
        select(PullListDecision)
        .where(PullListDecision.owner_user_id == owner_user_id)
        .order_by(PullListDecision.created_at.desc(), PullListDecision.id.desc())
    ).all()
    latest: dict[int, PullListDecision] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def _pull_list_issue_by_release(session: Session, *, owner_user_id: int) -> dict[int, PullListIssue]:
    rows = session.exec(
        select(PullListIssue)
        .join(PullList, PullList.id == PullListIssue.pull_list_id)
        .where(PullList.owner_user_id == owner_user_id)
    ).all()
    by_release: dict[int, PullListIssue] = {}
    for row in rows:
        rid = int(row.release_id)
        if rid not in by_release:
            by_release[rid] = row
    return by_release


def _sections_for_issue(
    *,
    foc_date: date | None,
    release_date: date | None,
    decision_type: str | None,
    today: date,
) -> list[FocDashboardSection]:
    sections: list[FocDashboardSection] = []
    df = days_until_foc(foc_date, today=today)
    dr = days_until_release(release_date, today=today)
    if foc_date is not None and df is not None and df < 0:
        sections.append(_SECTION_MISSED_FOC)
    if foc_date is not None and df is not None and 0 <= df <= 14:
        sections.append(_SECTION_ACTION_REQUIRED)
    if foc_date is not None and df is not None and 15 <= df <= 30:
        sections.append(_SECTION_UPCOMING_FOC)
    if release_date is not None and dr is not None and 0 <= dr <= 30:
        sections.append(_SECTION_UPCOMING_RELEASES)
    if decision_type == "WATCH":
        sections.append(_SECTION_WATCHLIST)
    return sections


def _collect_candidate_release_ids(
    session: Session,
    *,
    owner_user_id: int,
    today: date,
) -> set[int]:
    ids: set[int] = set(_latest_decision_rows(session, owner_user_id=owner_user_id).keys())
    ids.update(_pull_list_issue_by_release(session, owner_user_id=owner_user_id).keys())
    horizon = today.toordinal() + 30
    missed_cutoff = today.toordinal()
    for issue in session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all():
        if issue.foc_date is not None:
            ord_f = issue.foc_date.toordinal()
            if ord_f < missed_cutoff or ord_f <= horizon:
                ids.add(int(issue.id or 0))
        if issue.release_date is not None:
            ord_r = issue.release_date.toordinal()
            if missed_cutoff <= ord_r <= horizon:
                ids.add(int(issue.id or 0))
    return ids


def _build_item(
    session: Session,
    *,
    issue: ReleaseIssue,
    decision: PullListDecision | None,
    pl_issue: PullListIssue | None,
    today: date,
) -> FocDashboardItemRead | None:
    series = session.get(ReleaseSeries, issue.series_id)
    decision_type = decision.decision_type if decision else None
    sections = _sections_for_issue(
        foc_date=issue.foc_date,
        release_date=issue.release_date,
        decision_type=decision_type,
        today=today,
    )
    if not sections:
        return None
    reasons = _reasons_from_explanation(decision.explanation) if decision else []
    return FocDashboardItemRead(
        release_id=int(issue.id or 0),
        pull_list_issue_id=int(pl_issue.id) if pl_issue and pl_issue.id else None,
        decision_id=int(decision.id) if decision and decision.id else None,
        series_name=series.series_name if series else "",
        issue_number=issue.issue_number,
        title=issue.title,
        publisher=series.publisher if series else "",
        decision_type=decision_type,  # type: ignore[arg-type]
        confidence_score=float(decision.confidence_score) if decision else None,
        foc_date=issue.foc_date,
        release_date=issue.release_date,
        days_until_foc=days_until_foc(issue.foc_date, today=today),
        days_until_release=days_until_release(issue.release_date, today=today),
        foc_status=foc_status_bucket(issue.foc_date, today=today),
        reasons=reasons,
        sections=sections,
        on_pull_list=pl_issue is not None,
        pull_list_action_state=pl_issue.action_state if pl_issue else None,
    )


def _apply_filters(
    items: list[FocDashboardItemRead],
    *,
    decision_type: str | None,
    publisher: str | None,
    max_days_until_foc: int | None,
    max_days_until_release: int | None,
) -> list[FocDashboardItemRead]:
    filtered: list[FocDashboardItemRead] = []
    for item in items:
        if decision_type and (item.decision_type or "").upper() != decision_type.strip().upper():
            continue
        if publisher and publisher.strip().lower() not in item.publisher.lower():
            continue
        if max_days_until_foc is not None:
            if item.days_until_foc is None or item.days_until_foc > max_days_until_foc:
                continue
        if max_days_until_release is not None:
            if item.days_until_release is None or item.days_until_release > max_days_until_release:
                continue
        filtered.append(item)
    return filtered


def _sort_key(item: FocDashboardItemRead) -> tuple:
    return (
        item.days_until_foc if item.days_until_foc is not None else 9999,
        item.days_until_release if item.days_until_release is not None else 9999,
        item.release_id,
    )


def _build_dashboard_items(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_foc: int | None = None,
    max_days_until_release: int | None = None,
) -> list[FocDashboardItemRead]:
    ref = today or utc_today()
    decisions = _latest_decision_rows(session, owner_user_id=owner_user_id)
    pl_by_release = _pull_list_issue_by_release(session, owner_user_id=owner_user_id)
    items: list[FocDashboardItemRead] = []
    for release_id in sorted(_collect_candidate_release_ids(session, owner_user_id=owner_user_id, today=ref)):
        issue = session.get(ReleaseIssue, release_id)
        if issue is None or issue.owner_user_id != owner_user_id:
            continue
        built = _build_item(
            session,
            issue=issue,
            decision=decisions.get(release_id),
            pl_issue=pl_by_release.get(release_id),
            today=ref,
        )
        if built is not None:
            items.append(built)
    items = _apply_filters(
        items,
        decision_type=decision_type,
        publisher=publisher,
        max_days_until_foc=max_days_until_foc,
        max_days_until_release=max_days_until_release,
    )
    items.sort(key=_sort_key)
    return items


def _summary_from_items(items: list[FocDashboardItemRead]) -> FocDashboardSummaryRead:
    action = upcoming_foc = upcoming_rel = 0
    start_run = continue_run = watch = 0
    for item in items:
        if _SECTION_ACTION_REQUIRED in item.sections:
            action += 1
        if _SECTION_UPCOMING_FOC in item.sections:
            upcoming_foc += 1
        if _SECTION_UPCOMING_RELEASES in item.sections:
            upcoming_rel += 1
        if _SECTION_WATCHLIST in item.sections:
            watch += 1
        if item.decision_type == "START_RUN":
            start_run += 1
        elif item.decision_type == "CONTINUE_RUN":
            continue_run += 1
    return FocDashboardSummaryRead(
        action_required_count=action,
        start_run_count=start_run,
        continue_run_count=continue_run,
        watch_count=watch,
        upcoming_foc_count=upcoming_foc,
        upcoming_release_count=upcoming_rel,
    )


def _partition(items: list[FocDashboardItemRead]) -> FocDashboardRead:
    summary = _summary_from_items(items)
    action_required = [i for i in items if _SECTION_ACTION_REQUIRED in i.sections]
    upcoming_foc = [i for i in items if _SECTION_UPCOMING_FOC in i.sections]
    upcoming_releases = [i for i in items if _SECTION_UPCOMING_RELEASES in i.sections]
    missed_foc = [i for i in items if _SECTION_MISSED_FOC in i.sections]
    watchlist = [i for i in items if _SECTION_WATCHLIST in i.sections]
    return FocDashboardRead(
        summary=summary,
        action_required=action_required,
        upcoming_foc=upcoming_foc,
        upcoming_releases=upcoming_releases,
        missed_foc=missed_foc,
        watchlist=watchlist,
    )


def get_foc_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_foc: int | None = None,
    max_days_until_release: int | None = None,
) -> FocDashboardRead:
    items = _build_dashboard_items(
        session,
        owner_user_id=owner_user_id,
        today=today,
        decision_type=decision_type,
        publisher=publisher,
        max_days_until_foc=max_days_until_foc,
        max_days_until_release=max_days_until_release,
    )
    return _partition(items)


def get_foc_dashboard_summary(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_foc: int | None = None,
    max_days_until_release: int | None = None,
) -> FocDashboardSummaryRead:
    items = _build_dashboard_items(
        session,
        owner_user_id=owner_user_id,
        today=today,
        decision_type=decision_type,
        publisher=publisher,
        max_days_until_foc=max_days_until_foc,
        max_days_until_release=max_days_until_release,
    )
    return _summary_from_items(items)


def list_foc_dashboard_actions(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_foc: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> FocDashboardListResponse:
    dashboard = get_foc_dashboard(
        session,
        owner_user_id=owner_user_id,
        today=today,
        decision_type=decision_type,
        publisher=publisher,
        max_days_until_foc=max_days_until_foc,
    )
    combined = dashboard.action_required + dashboard.missed_foc
    combined.sort(key=_sort_key)
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    total = len(combined)
    return FocDashboardListResponse(items=combined[offset : offset + limit], total_items=total, limit=limit, offset=offset)


def list_foc_dashboard_releases(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_release: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> FocDashboardListResponse:
    dashboard = get_foc_dashboard(
        session,
        owner_user_id=owner_user_id,
        today=today,
        decision_type=decision_type,
        publisher=publisher,
        max_days_until_release=max_days_until_release,
    )
    items = dashboard.upcoming_releases
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    total = len(items)
    return FocDashboardListResponse(items=items[offset : offset + limit], total_items=total, limit=limit, offset=offset)
