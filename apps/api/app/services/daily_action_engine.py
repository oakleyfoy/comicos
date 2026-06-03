from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, select

from app.models.daily_action_engine import DailyCollectorAction
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.unified_collector_intelligence import UnifiedCollectorRecommendation
from app.schemas.daily_action_engine import DailyActionSummaryRead, DailyCollectorActionRead
from app.services.foc_dates import days_until_foc, utc_today
from app.services.grade_before_sell import _latest_rows as _latest_grade_rows
from app.services.recommendation_catalog_quality import (
    build_forward_release_title_index,
    title_passes_top_recommendation_quality,
)
from app.services.recommendation_latest_rows import latest_by_key_bounded_scan
from app.services.unified_collector_intelligence import (
    _latest_recommendation_rows,
    generate_unified_collector_recommendations,
)

ACTION_PREORDER = "PREORDER"
ACTION_ACQUIRE = "ACQUIRE"
ACTION_GRADE = "GRADE"
ACTION_SELL = "SELL"
ACTION_REBALANCE = "REBALANCE"
ACTION_REVIEW = "REVIEW"
ACTION_WATCH = "WATCH"

_UNIFIED_TO_ACTION = {
    "PREORDER": ACTION_PREORDER,
    "ACQUIRE": ACTION_ACQUIRE,
    "GRADE": ACTION_GRADE,
    "SELL": ACTION_SELL,
    "REBALANCE": ACTION_REBALANCE,
    "WATCH": ACTION_WATCH,
}


@dataclass(frozen=True)
class _ActionDraft:
    action_type: str
    title: str
    priority_score: float
    confidence_score: float
    due_date: date | None
    rationale: str
    source_recommendation_id: int | None
    source_systems: list[str]


def _clamp_priority(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


def _clamp_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _parse_title(title: str) -> tuple[str, str]:
    parts = title.split("#", 1)
    series = parts[0].strip()
    issue = parts[1].strip() if len(parts) > 1 else ""
    return series, issue


def _foc_due_date_from_index(
    title: str,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
) -> date | None:
    title_key = title.strip().lower()
    if title_key.endswith(" (variants)"):
        title_key = title_key[: -len(" (variants)")]
    pair = release_index.get(title_key)
    if pair is None:
        return None
    issue, _ = pair
    return issue.foc_date


def _foc_due_date(session: Session, *, owner_user_id: int, title: str) -> date | None:
    """Legacy path — prefer _foc_due_date_from_index when index is already loaded."""
    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    return _foc_due_date_from_index(title, release_index)


def _priority_with_due(*, action_type: str, base: float, due_date: date | None) -> float:
    priority = base
    if action_type == ACTION_PREORDER and due_date is not None:
        days = days_until_foc(due_date, today=utc_today())
        if days is not None and days <= 3:
            priority += 6.0
        elif days is not None and days <= 7:
            priority += 3.0
    if action_type == ACTION_ACQUIRE and base >= 88.0:
        priority += 2.0
    if action_type == ACTION_GRADE and base >= 78.0:
        priority += 1.5
    if action_type == ACTION_SELL and base >= 70.0:
        priority += 1.0
    if action_type in {ACTION_WATCH, ACTION_REVIEW}:
        priority = min(priority, 60.0)
    return _clamp_priority(min(94.0, priority))


def _confidence_from_sources(base: float, sources: list[str]) -> float:
    boost = min(0.08, 0.022 * max(0, len(sources) - 1))
    return _clamp_confidence(min(0.96, base + boost))


def _build_drafts(session: Session, *, owner_user_id: int, refresh_unified: bool = True) -> list[_ActionDraft]:
    if refresh_unified:
        generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    drafts: list[_ActionDraft] = []
    seen_titles: set[tuple[str, str]] = set()

    for row in _latest_recommendation_rows(session, owner_user_id=owner_user_id).values():
        if not title_passes_top_recommendation_quality(
            row.title,
            session=session,
            owner_user_id=owner_user_id,
            release_index=release_index,
        ):
            continue
        action_type = _UNIFIED_TO_ACTION.get(row.recommendation_type, ACTION_WATCH)
        sources = list(row.source_systems or [])
        due = (
            _foc_due_date_from_index(row.title, release_index)
            if action_type == ACTION_PREORDER
            else None
        )
        priority = _priority_with_due(
            action_type=action_type,
            base=float(row.priority_score),
            due_date=due,
        )
        confidence = _confidence_from_sources(float(row.confidence_score), sources)
        rationale = row.rationale or "Daily action from unified collector intelligence."
        if due is not None and action_type == ACTION_PREORDER:
            days = days_until_foc(due, today=utc_today())
            if days is not None:
                rationale = f"FOC in {days} days. {rationale}".strip()
        drafts.append(
            _ActionDraft(
                action_type=action_type,
                title=row.title,
                priority_score=priority,
                confidence_score=confidence,
                due_date=due,
                rationale=rationale,
                source_recommendation_id=int(row.id) if row.id else None,
                source_systems=sources,
            )
        )
        seen_titles.add((action_type, row.title.strip().lower()))

    for grow in _latest_grade_rows(session, owner_user_id=owner_user_id).values():
        if grow.recommendation != "HOLD_FOR_REVIEW":
            continue
        from app.services.grade_before_sell import _to_read as gbs_read

        read = gbs_read(session, row=grow)
        title = f"{read.title} #{read.issue_number}".strip() if read.issue_number else read.title
        key = (ACTION_REVIEW, title.strip().lower())
        if key in seen_titles:
            continue
        drafts.append(
            _ActionDraft(
                action_type=ACTION_REVIEW,
                title=title,
                priority_score=48.0,
                confidence_score=_clamp_confidence(float(grow.confidence_score)),
                due_date=None,
                rationale=grow.rationale or "Requires review before grade or sell decision.",
                source_recommendation_id=None,
                source_systems=["P56_EXIT"],
            )
        )

    drafts.sort(
        key=lambda d: (
            -d.priority_score,
            d.due_date or date.max,
            -d.confidence_score,
            d.title.lower(),
        )
    )
    return drafts


def _latest_action_rows(
    session: Session,
    *,
    owner_user_id: int,
    scan_limit: int = 8000,
) -> dict[tuple[str, str], DailyCollectorAction]:
    return latest_by_key_bounded_scan(
        session,
        model=DailyCollectorAction,
        owner_user_id=owner_user_id,
        owner_field="owner_user_id",
        key_fn=lambda row: (row.action_type, row.title.strip().lower()),
        scan_limit=scan_limit,
    )


def _matches_idempotency(prior: DailyCollectorAction, draft: _ActionDraft) -> bool:
    prior_due = prior.due_date
    draft_due = draft.due_date
    return (
        prior.action_type == draft.action_type
        and prior.title == draft.title
        and abs(float(prior.priority_score) - float(draft.priority_score)) < 1e-9
        and abs(float(prior.confidence_score) - float(draft.confidence_score)) < 1e-9
        and prior_due == draft_due
        and prior.rationale == draft.rationale
    )


def generate_daily_actions(session: Session, *, owner_user_id: int, refresh_unified: bool = True) -> int:
    drafts = _build_drafts(session, owner_user_id=owner_user_id, refresh_unified=refresh_unified)
    latest = _latest_action_rows(session, owner_user_id=owner_user_id)
    created = 0
    for draft in drafts:
        key = (draft.action_type, draft.title.strip().lower())
        prior = latest.get(key)
        if prior is not None and _matches_idempotency(prior, draft):
            continue
        row = DailyCollectorAction(
            owner_user_id=owner_user_id,
            action_type=draft.action_type,
            priority_score=draft.priority_score,
            confidence_score=draft.confidence_score,
            due_date=draft.due_date,
            title=draft.title,
            rationale=draft.rationale,
            source_recommendation_id=draft.source_recommendation_id,
            source_systems=draft.source_systems,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def _to_read(row: DailyCollectorAction) -> DailyCollectorActionRead:
    return DailyCollectorActionRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        action_type=row.action_type,
        priority_score=float(row.priority_score),
        confidence_score=float(row.confidence_score),
        due_date=row.due_date,
        title=row.title,
        rationale=row.rationale,
        source_recommendation_id=row.source_recommendation_id,
        source_systems=list(row.source_systems or []),
        created_at=row.created_at,
    )


def _sort_key(row: DailyCollectorAction) -> tuple:
    due_ord = row.due_date.toordinal() if row.due_date else 999999
    return (
        -float(row.priority_score),
        due_ord,
        -float(row.confidence_score),
        row.created_at,
        -(int(row.id or 0)),
    )


def list_latest_daily_actions(
    session: Session,
    *,
    owner_user_id: int,
    action_type: str | None = None,
    priority_min: float | None = None,
    due_before: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DailyCollectorActionRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_action_rows(session, owner_user_id=owner_user_id)
    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    rows: list[DailyCollectorAction] = []
    for row in latest.values():
        if not title_passes_top_recommendation_quality(
            row.title,
            session=session,
            owner_user_id=owner_user_id,
            release_index=release_index,
        ):
            continue
        if action_type and row.action_type != action_type.strip().upper():
            continue
        if priority_min is not None and float(row.priority_score) < float(priority_min):
            continue
        if due_before is not None and row.due_date is not None and row.due_date > due_before:
            continue
        rows.append(row)
    rows.sort(key=_sort_key)
    items = [_to_read(row) for row in rows]
    total = len(items)
    return items[offset : offset + limit], total


def get_daily_action_summary(session: Session, *, owner_user_id: int) -> DailyActionSummaryRead:
    items, total = list_latest_daily_actions(session, owner_user_id=owner_user_id, limit=500, offset=0)
    critical = sum(1 for i in items if i.priority_score >= 90.0)
    return DailyActionSummaryRead(
        total_actions=total,
        critical_actions=critical,
        preorder_actions=sum(1 for i in items if i.action_type == ACTION_PREORDER),
        acquisition_actions=sum(1 for i in items if i.action_type == ACTION_ACQUIRE),
        grading_actions=sum(1 for i in items if i.action_type == ACTION_GRADE),
        sell_actions=sum(1 for i in items if i.action_type == ACTION_SELL),
        rebalance_actions=sum(1 for i in items if i.action_type == ACTION_REBALANCE),
        watch_actions=sum(1 for i in items if i.action_type in {ACTION_WATCH, ACTION_REVIEW}),
    )


def refresh_and_list_latest_daily_actions(
    session: Session,
    *,
    owner_user_id: int,
    action_type: str | None = None,
    priority_min: float | None = None,
    due_before: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DailyCollectorActionRead], int]:
    generate_daily_actions(session, owner_user_id=owner_user_id)
    return list_latest_daily_actions(
        session,
        owner_user_id=owner_user_id,
        action_type=action_type,
        priority_min=priority_min,
        due_before=due_before,
        limit=limit,
        offset=offset,
    )
