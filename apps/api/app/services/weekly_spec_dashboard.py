from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.models.future_release_action import FutureReleaseAction
from app.models.spec_input import SpecInput
from app.models.top_spec_pick import TopSpecPick
from app.schemas.weekly_spec_dashboard import (
    WeeklySpecDashboardItemRead,
    WeeklySpecDashboardRead,
    WeeklySpecDashboardSummaryRead,
)
from app.services.spec_baseline_engine import _signal_flags
from app.services.top_spec_picks import _to_read as top_spec_pick_to_read

SECTION_LIMIT = 20
HIGH_CONFIDENCE_THRESHOLD = 0.75
HIGH_RISK_HIGH_REWARD_MIN_SCORE = 55.0
FOC_APPROACHING_DAYS = 7


def _foc_urgency_label(foc_date: date | None) -> str:
    if foc_date is None:
        return "NO_FOC"
    today = datetime.now(timezone.utc).date()
    days = (foc_date - today).days
    if days < 0:
        return "FOC_PASSED"
    if days <= 3:
        return "FOC_IMMINENT"
    if days <= 7:
        return "FOC_APPROACHING"
    if days <= 14:
        return "FOC_HORIZON"
    return "FOC_SCHEDULED"


def _is_foc_approaching(foc_date: date | None) -> bool:
    if foc_date is None:
        return False
    today = datetime.now(timezone.utc).date()
    days = (foc_date - today).days
    return 0 <= days <= FOC_APPROACHING_DAYS


def _signal_types_from_flags(flags: dict[str, bool]) -> list[str]:
    types: list[str] = []
    if flags.get("number_one"):
        types.append("NUMBER_ONE")
    if flags.get("first_appearance"):
        types.append("FIRST_APPEARANCE")
    if flags.get("ratio_variant"):
        types.append("RATIO_VARIANT")
    if flags.get("milestone"):
        types.append("MILESTONE")
    if flags.get("anniversary"):
        types.append("ANNIVERSARY")
    if flags.get("key_event"):
        types.append("KEY_EVENT")
    if flags.get("facsimile"):
        types.append("FACSIMILE")
    return types


def _latest_future_actions(session: Session, *, owner_user_id: int) -> dict[int, FutureReleaseAction]:
    rows = session.exec(
        select(FutureReleaseAction)
        .where(FutureReleaseAction.owner_user_id == owner_user_id)
        .where(FutureReleaseAction.release_id.is_not(None))
        .order_by(FutureReleaseAction.created_at.desc(), FutureReleaseAction.id.desc())
    ).all()
    latest: dict[int, FutureReleaseAction] = {}
    for row in rows:
        if row.release_id is None:
            continue
        rid = int(row.release_id)
        if rid not in latest:
            latest[rid] = row
    return latest


def _load_dashboard_items(session: Session, *, owner_user_id: int) -> list[WeeklySpecDashboardItemRead]:
    picks = session.exec(
        select(TopSpecPick)
        .where(TopSpecPick.owner_user_id == owner_user_id)
        .order_by(TopSpecPick.rank.asc(), TopSpecPick.id.asc())
    ).all()
    if not picks:
        return []

    spec_inputs = {
        int(row.id or 0): row
        for row in session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
        if row.id is not None
    }
    actions = _latest_future_actions(session, owner_user_id=owner_user_id)

    items: list[WeeklySpecDashboardItemRead] = []
    for pick in picks:
        base = top_spec_pick_to_read(pick)
        spec_input = spec_inputs.get(int(pick.spec_input_id))
        signal_types: list[str] = []
        if spec_input is not None:
            try:
                summary = json.loads(spec_input.signal_summary or "{}")
            except json.JSONDecodeError:
                summary = {}
            normalized = summary.get("normalized_signals", [])
            if isinstance(normalized, list):
                for row in normalized:
                    if row.get("kind") == "industry_signal" and row.get("signal_type"):
                        signal_types.append(str(row["signal_type"]).upper())
            flags = _signal_flags(normalized if isinstance(normalized, list) else [], issue_number=pick.issue_number)
            for token in _signal_types_from_flags(flags):
                if token not in signal_types:
                    signal_types.append(token)
            signal_types = sorted(set(signal_types))

        action = actions.get(int(pick.release_id)) if pick.release_id is not None else None
        action_type = action.action_type if action else None
        if action_type == "PREORDER_NOW" and "PREORDER_NOW" not in signal_types:
            signal_types.append("PREORDER_NOW")

        items.append(
            WeeklySpecDashboardItemRead(
                **base.model_dump(),
                signal_types=signal_types,
                foc_urgency_label=_foc_urgency_label(pick.foc_date),
                future_release_action=action_type,
            )
        )
    return items


def _has_signal(item: WeeklySpecDashboardItemRead, token: str) -> bool:
    return token in item.signal_types


def _filter_section(items: list[WeeklySpecDashboardItemRead], predicate) -> list[WeeklySpecDashboardItemRead]:
    return [row for row in items if predicate(row)][:SECTION_LIMIT]


def build_weekly_spec_dashboard_summary(session: Session, *, owner_user_id: int) -> WeeklySpecDashboardSummaryRead:
    items = _load_dashboard_items(session, owner_user_id=owner_user_id)
    if not items:
        return WeeklySpecDashboardSummaryRead()

    confidences = [float(row.confidence_score) for row in items]
    return WeeklySpecDashboardSummaryRead(
        top_picks_count=len(items),
        preorder_now_count=sum(
            1 for row in items if row.future_release_action == "PREORDER_NOW" or _has_signal(row, "PREORDER_NOW")
        ),
        average_confidence=round(sum(confidences) / len(confidences), 3),
        high_risk_count=sum(1 for row in items if row.risk_level == "HIGH"),
        number_one_issues_count=sum(1 for row in items if _has_signal(row, "NUMBER_ONE")),
        ratio_variant_count=sum(1 for row in items if _has_signal(row, "RATIO_VARIANT")),
        first_appearance_count=sum(1 for row in items if _has_signal(row, "FIRST_APPEARANCE")),
        foc_approaching_count=sum(
            1 for row in items if row.foc_urgency_label in {"FOC_IMMINENT", "FOC_APPROACHING"}
        ),
    )


def build_weekly_spec_dashboard(session: Session, *, owner_user_id: int) -> WeeklySpecDashboardRead:
    items = _load_dashboard_items(session, owner_user_id=owner_user_id)
    summary = build_weekly_spec_dashboard_summary(session, owner_user_id=owner_user_id)

    publisher_breakdown: dict[str, int] = {}
    signal_breakdown: dict[str, int] = {}
    for row in items:
        publisher = row.publisher.strip() or "Unknown"
        publisher_breakdown[publisher] = publisher_breakdown.get(publisher, 0) + 1
        for signal in row.signal_types:
            signal_breakdown[signal] = signal_breakdown.get(signal, 0) + 1

    def preorder_now(row: WeeklySpecDashboardItemRead) -> bool:
        return row.future_release_action == "PREORDER_NOW" or _has_signal(row, "PREORDER_NOW")

    return WeeklySpecDashboardRead(
        summary=summary,
        publisher_breakdown=dict(sorted(publisher_breakdown.items(), key=lambda pair: (-pair[1], pair[0].lower()))),
        signal_breakdown=dict(sorted(signal_breakdown.items(), key=lambda pair: (-pair[1], pair[0]))),
        top_20_preorder=items[:SECTION_LIMIT],
        preorder_now=_filter_section(items, preorder_now),
        high_confidence=_filter_section(items, lambda row: float(row.confidence_score) >= HIGH_CONFIDENCE_THRESHOLD),
        high_risk_high_reward=_filter_section(
            items,
            lambda row: row.risk_level == "HIGH" and float(row.final_score) >= HIGH_RISK_HIGH_REWARD_MIN_SCORE,
        ),
        number_one_issues=_filter_section(items, lambda row: _has_signal(row, "NUMBER_ONE")),
        ratio_variants=_filter_section(items, lambda row: _has_signal(row, "RATIO_VARIANT")),
        first_appearances=_filter_section(items, lambda row: _has_signal(row, "FIRST_APPEARANCE")),
        milestones=_filter_section(
            items,
            lambda row: _has_signal(row, "MILESTONE") or _has_signal(row, "ANNIVERSARY"),
        ),
    )
