from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session

from app.schemas.exit_dashboard import (
    ExitDashboardActionsRead,
    ExitDashboardItemRead,
    ExitDashboardRead,
    ExitDashboardSummaryRead,
    SECTION_CAPITAL,
    SECTION_REVIEW,
    SECTION_TOP_GRADE,
    SECTION_TOP_REBALANCE,
    SECTION_TOP_SELL,
)
from app.services.exit_candidates import _latest_exit_candidate_rows, _to_read as exit_to_read
from app.services.grade_before_sell import _latest_rows as latest_grade_rows, _to_read as grade_to_read
from app.services.hold_sell_intelligence import _latest_hold_sell_rows, _to_read as hold_to_read
from app.services.portfolio_rebalancing import _latest_rows as latest_rebalance_rows, _to_read as rebalance_to_read
from app.services.sell_candidates import _latest_sell_candidate_rows, _to_read as sell_to_read

TOP_N = 15
CAPITAL_CANDIDATE_MIN_SCORE = 25.0
CAPITAL_GAIN_MIN = 15.0


@dataclass(frozen=True)
class _Sortable:
    payload: ExitDashboardItemRead
    primary: float
    confidence: float
    capital: float
    created_at: datetime
    item_id: int


def _parse_created_at(value: str) -> datetime:
    if not value:
        return datetime.fromisoformat("1970-01-01T00:00:00+00:00")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromisoformat("1970-01-01T00:00:00+00:00")


def _sort_key(row: _Sortable) -> tuple:
    return (
        -row.primary,
        -row.confidence,
        -row.capital,
        row.created_at.isoformat(),
        row.item_id,
    )


def _sort_and_trim(items: list[_Sortable], *, limit: int = TOP_N) -> list[ExitDashboardItemRead]:
    return [r.payload for r in sorted(items, key=_sort_key)[:limit]]


def _apply_filters(
    *,
    publisher: str | None,
    recommendation: str | None,
    action: str | None,
    score_min: float | None,
    item: ExitDashboardItemRead,
) -> bool:
    if publisher:
        needle = publisher.strip().lower()
        if needle not in item.publisher.lower() and needle not in item.title.lower():
            return False
    if recommendation:
        rec = (item.recommendation or "").upper()
        if rec != recommendation.strip().upper():
            return False
    if action:
        act = (item.action or item.recommendation or "").upper()
        if act != action.strip().upper():
            return False
    if score_min is not None and (item.priority_score or 0.0) < float(score_min):
        return False
    return True


def _build_context(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None,
    recommendation: str | None,
    action: str | None,
    score_min: float | None,
) -> tuple[
    list[_Sortable],
    list[_Sortable],
    list[_Sortable],
    list[_Sortable],
    list[_Sortable],
    ExitDashboardSummaryRead,
]:
    exit_latest = _latest_exit_candidate_rows(session, owner_user_id=owner_user_id)
    hold_latest = _latest_hold_sell_rows(session, owner_user_id=owner_user_id)
    grade_latest = latest_grade_rows(session, owner_user_id=owner_user_id)
    rebalance_latest = latest_rebalance_rows(session, owner_user_id=owner_user_id)
    sell_latest = _latest_sell_candidate_rows(session, owner_user_id=owner_user_id)

    sell_items: list[_Sortable] = []
    watch_count = 0
    hold_count = 0
    sell_count = 0
    capital_recovery_total = 0.0

    for row in hold_latest.values():
        read = hold_to_read(session, row=row)
        rec = read.recommendation
        if rec == "SELL":
            sell_count += 1
        elif rec == "WATCH":
            watch_count += 1
        else:
            hold_count += 1
        if rec == "SELL" and read.unrealized_gain > 0:
            capital_recovery_total += read.unrealized_gain

        if rec == "SELL":
            payload = ExitDashboardItemRead(
                section=SECTION_TOP_SELL,
                item_type="hold_sell",
                item_id=read.id,
                inventory_item_id=read.inventory_item_id,
                publisher=read.publisher,
                series_name=read.title,
                issue_number=read.issue_number,
                title=f"{read.title} #{read.issue_number}".strip(),
                recommendation=rec,
                priority_score=read.conviction_score,
                confidence_score=read.confidence_score,
                capital_value=read.unrealized_gain,
                rationale=read.rationale,
                created_at=read.created_at,
            )
            if _apply_filters(
                publisher=publisher,
                recommendation=recommendation,
                action=action,
                score_min=score_min,
                item=payload,
            ):
                sell_items.append(
                    _Sortable(
                        payload=payload,
                        primary=read.conviction_score,
                        confidence=read.confidence_score,
                        capital=read.unrealized_gain,
                        created_at=_parse_created_at(read.created_at),
                        item_id=read.id,
                    )
                )

    grade_items: list[_Sortable] = []
    grade_before_count = 0
    sell_raw_count = 0
    for row in grade_latest.values():
        read = grade_to_read(session, row=row)
        if read.recommendation == "GRADE_BEFORE_SELL":
            grade_before_count += 1
        elif read.recommendation == "SELL_RAW":
            sell_raw_count += 1
        if read.recommendation == "GRADE_BEFORE_SELL":
            payload = ExitDashboardItemRead(
                section=SECTION_TOP_GRADE,
                item_type="grade_before_sell",
                item_id=read.id,
                inventory_item_id=read.inventory_item_id,
                publisher=read.publisher,
                series_name=read.title,
                issue_number=read.issue_number,
                title=f"{read.title} #{read.issue_number}".strip(),
                recommendation=read.recommendation,
                priority_score=read.expected_roi * 25.0,
                confidence_score=read.confidence_score,
                capital_value=read.expected_value_gain,
                rationale=read.rationale,
                created_at=read.created_at,
            )
            if _apply_filters(
                publisher=publisher,
                recommendation=recommendation,
                action=action,
                score_min=score_min,
                item=payload,
            ):
                grade_items.append(
                    _Sortable(
                        payload=payload,
                        primary=read.expected_roi,
                        confidence=read.confidence_score,
                        capital=read.expected_value_gain,
                        created_at=_parse_created_at(read.created_at),
                        item_id=read.id,
                    )
                )

    rebalance_items: list[_Sortable] = []
    rebalance_action_count = 0
    for row in rebalance_latest.values():
        read = rebalance_to_read(row)
        if read.recommended_action in {"REDUCE_EXPOSURE", "REVIEW_POSITION"}:
            rebalance_action_count += 1
        if read.recommended_action in {"REDUCE_EXPOSURE", "REVIEW_POSITION"}:
            payload = ExitDashboardItemRead(
                section=SECTION_TOP_REBALANCE,
                item_type="portfolio_rebalance",
                item_id=read.id,
                publisher=read.publisher,
                title=read.target_label,
                recommendation=read.rebalance_type,
                action=read.recommended_action,
                priority_score=read.priority_score,
                confidence_score=read.confidence_score,
                capital_value=read.exposure_value,
                rationale=read.rationale,
                created_at=read.created_at,
            )
            if _apply_filters(
                publisher=publisher,
                recommendation=recommendation,
                action=action,
                score_min=score_min,
                item=payload,
            ):
                rebalance_items.append(
                    _Sortable(
                        payload=payload,
                        primary=read.priority_score,
                        confidence=read.confidence_score,
                        capital=read.exposure_value,
                        created_at=_parse_created_at(read.created_at),
                        item_id=read.id,
                    )
                )

    capital_items: list[_Sortable] = []
    seen_capital: set[tuple[str, int]] = set()

    for row in exit_latest.values():
        read = exit_to_read(session, row=row)
        if read.candidate_score < CAPITAL_CANDIDATE_MIN_SCORE:
            continue
        key = ("exit_candidate", read.inventory_item_id)
        if key in seen_capital:
            continue
        seen_capital.add(key)
        payload = ExitDashboardItemRead(
            section=SECTION_CAPITAL,
            item_type="exit_candidate",
            item_id=read.id,
            inventory_item_id=read.inventory_item_id,
            publisher=read.publisher,
            series_name=read.title,
            issue_number=read.issue_number,
            title=f"{read.title} #{read.issue_number}".strip(),
            recommendation=read.candidate_reason,
            priority_score=read.candidate_score,
            confidence_score=read.confidence_score,
            capital_value=read.unrealized_gain,
            rationale=f"Exit candidate ({read.candidate_reason}) with score {read.candidate_score:.1f}.",
            created_at=read.created_at,
        )
        if _apply_filters(
            publisher=publisher,
            recommendation=recommendation,
            action=action,
            score_min=score_min,
            item=payload,
        ):
            capital_items.append(
                _Sortable(
                    payload=payload,
                    primary=read.candidate_score,
                    confidence=read.confidence_score,
                    capital=read.unrealized_gain,
                    created_at=_parse_created_at(read.created_at),
                    item_id=read.id,
                )
            )

    for row in hold_latest.values():
        read = hold_to_read(session, row=row)
        if read.unrealized_gain < CAPITAL_GAIN_MIN:
            continue
        if read.recommendation not in {"SELL", "WATCH"}:
            continue
        key = ("hold_sell", read.inventory_item_id)
        if key in seen_capital:
            continue
        seen_capital.add(key)
        payload = ExitDashboardItemRead(
            section=SECTION_CAPITAL,
            item_type="hold_sell",
            item_id=read.id,
            inventory_item_id=read.inventory_item_id,
            publisher=read.publisher,
            series_name=read.title,
            issue_number=read.issue_number,
            title=f"{read.title} #{read.issue_number}".strip(),
            recommendation=read.recommendation,
            priority_score=read.conviction_score,
            confidence_score=read.confidence_score,
            capital_value=read.unrealized_gain,
            rationale=read.rationale,
            created_at=read.created_at,
        )
        if _apply_filters(
            publisher=publisher,
            recommendation=recommendation,
            action=action,
            score_min=score_min,
            item=payload,
        ):
            capital_items.append(
                _Sortable(
                    payload=payload,
                    primary=read.conviction_score,
                    confidence=read.confidence_score,
                    capital=read.unrealized_gain,
                    created_at=_parse_created_at(read.created_at),
                    item_id=read.id,
                )
            )

    for row in sell_latest.values():
        if row.estimated_profit < CAPITAL_GAIN_MIN:
            continue
        read = sell_to_read(session, row=row)
        key = ("sell_candidate", read.inventory_item_id)
        if key in seen_capital:
            continue
        seen_capital.add(key)
        payload = ExitDashboardItemRead(
            section=SECTION_CAPITAL,
            item_type="sell_candidate",
            item_id=read.id,
            inventory_item_id=read.inventory_item_id,
            publisher=read.publisher,
            series_name=read.title,
            issue_number=read.issue_number,
            title=f"{read.title} #{read.issue_number}".strip(),
            recommendation=read.recommendation,
            priority_score=read.confidence_score * 100.0,
            confidence_score=read.confidence_score,
            capital_value=read.estimated_profit,
            rationale=read.rationale,
            created_at=read.created_at,
        )
        if _apply_filters(
            publisher=publisher,
            recommendation=recommendation,
            action=action,
            score_min=score_min,
            item=payload,
        ):
            capital_items.append(
                _Sortable(
                    payload=payload,
                    primary=read.confidence_score * 100.0,
                    confidence=read.confidence_score,
                    capital=read.estimated_profit,
                    created_at=_parse_created_at(read.created_at),
                    item_id=read.id,
                )
            )

    review_items: list[_Sortable] = []
    review_count = 0

    for row in hold_latest.values():
        read = hold_to_read(session, row=row)
        if read.recommendation != "WATCH":
            continue
        review_count += 1
        payload = ExitDashboardItemRead(
            section=SECTION_REVIEW,
            item_type="hold_sell",
            item_id=read.id,
            inventory_item_id=read.inventory_item_id,
            publisher=read.publisher,
            series_name=read.title,
            issue_number=read.issue_number,
            title=f"{read.title} #{read.issue_number}".strip(),
            recommendation=read.recommendation,
            priority_score=read.conviction_score,
            confidence_score=read.confidence_score,
            capital_value=read.unrealized_gain,
            rationale=read.rationale,
            created_at=read.created_at,
        )
        if _apply_filters(
            publisher=publisher,
            recommendation=recommendation,
            action=action,
            score_min=score_min,
            item=payload,
        ):
            review_items.append(
                _Sortable(
                    payload=payload,
                    primary=read.conviction_score,
                    confidence=read.confidence_score,
                    capital=read.unrealized_gain,
                    created_at=_parse_created_at(read.created_at),
                    item_id=read.id,
                )
            )

    for row in grade_latest.values():
        read = grade_to_read(session, row=row)
        if read.recommendation != "HOLD_FOR_REVIEW":
            continue
        review_count += 1
        payload = ExitDashboardItemRead(
            section=SECTION_REVIEW,
            item_type="grade_before_sell",
            item_id=read.id,
            inventory_item_id=read.inventory_item_id,
            publisher=read.publisher,
            series_name=read.title,
            issue_number=read.issue_number,
            title=f"{read.title} #{read.issue_number}".strip(),
            recommendation=read.recommendation,
            priority_score=read.expected_roi,
            confidence_score=read.confidence_score,
            capital_value=read.expected_value_gain,
            rationale=read.rationale,
            created_at=read.created_at,
        )
        if _apply_filters(
            publisher=publisher,
            recommendation=recommendation,
            action=action,
            score_min=score_min,
            item=payload,
        ):
            review_items.append(
                _Sortable(
                    payload=payload,
                    primary=read.expected_roi,
                    confidence=read.confidence_score,
                    capital=read.expected_value_gain,
                    created_at=_parse_created_at(read.created_at),
                    item_id=read.id,
                )
            )

    for row in rebalance_latest.values():
        read = rebalance_to_read(row)
        if read.recommended_action != "REVIEW_POSITION":
            continue
        review_count += 1
        payload = ExitDashboardItemRead(
            section=SECTION_REVIEW,
            item_type="portfolio_rebalance",
            item_id=read.id,
            title=read.target_label,
            publisher=read.publisher,
            recommendation=read.rebalance_type,
            action=read.recommended_action,
            priority_score=read.priority_score,
            confidence_score=read.confidence_score,
            capital_value=read.exposure_value,
            rationale=read.rationale,
            created_at=read.created_at,
        )
        if _apply_filters(
            publisher=publisher,
            recommendation=recommendation,
            action=action,
            score_min=score_min,
            item=payload,
        ):
            review_items.append(
                _Sortable(
                    payload=payload,
                    primary=read.priority_score,
                    confidence=read.confidence_score,
                    capital=read.exposure_value,
                    created_at=_parse_created_at(read.created_at),
                    item_id=read.id,
                )
            )

    summary = ExitDashboardSummaryRead(
        total_exit_candidates=len(exit_latest),
        sell_recommendations=sell_count,
        watch_recommendations=watch_count,
        hold_recommendations=hold_count,
        grade_before_sell_recommendations=grade_before_count,
        sell_raw_recommendations=sell_raw_count,
        rebalance_actions=rebalance_action_count,
        estimated_capital_recovery=round(capital_recovery_total, 2),
        review_required_count=review_count,
    )
    return sell_items, grade_items, rebalance_items, capital_items, review_items, summary


def get_exit_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None = None,
    recommendation: str | None = None,
    action: str | None = None,
    score_min: float | None = None,
) -> ExitDashboardRead:
    sell_items, grade_items, rebalance_items, capital_items, review_items, summary = _build_context(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        recommendation=recommendation,
        action=action,
        score_min=score_min,
    )
    return ExitDashboardRead(
        summary=summary,
        top_sell_recommendations=_sort_and_trim(sell_items),
        top_grade_before_sell=_sort_and_trim(grade_items),
        top_rebalance_actions=_sort_and_trim(rebalance_items),
        capital_recovery=_sort_and_trim(capital_items),
        review_required=_sort_and_trim(review_items),
    )


def get_exit_dashboard_summary(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None = None,
    recommendation: str | None = None,
    action: str | None = None,
    score_min: float | None = None,
) -> ExitDashboardSummaryRead:
    *_, summary = _build_context(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        recommendation=recommendation,
        action=action,
        score_min=score_min,
    )
    return summary


def get_exit_dashboard_actions(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None = None,
    recommendation: str | None = None,
    action: str | None = None,
    score_min: float | None = None,
) -> ExitDashboardActionsRead:
    dashboard = get_exit_dashboard(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        recommendation=recommendation,
        action=action,
        score_min=score_min,
    )
    urgent: list[ExitDashboardItemRead] = []
    urgent.extend(dashboard.top_sell_recommendations)
    urgent.extend(dashboard.top_grade_before_sell)
    urgent.extend([i for i in dashboard.top_rebalance_actions if i.action == "REDUCE_EXPOSURE"])
    urgent.extend(dashboard.capital_recovery[:5])
    urgent.extend(dashboard.review_required)

    seen: set[tuple[str, int]] = set()
    deduped: list[ExitDashboardItemRead] = []
    for item in urgent:
        key = (item.item_type, item.item_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    sortable: list[_Sortable] = []
    for item in deduped:
        sortable.append(
            _Sortable(
                payload=item,
                primary=float(item.priority_score or 0),
                confidence=float(item.confidence_score or 0),
                capital=float(item.capital_value or 0),
                created_at=_parse_created_at(item.created_at),
                item_id=item.item_id,
            )
        )
    return ExitDashboardActionsRead(priority_exit_actions=_sort_and_trim(sortable, limit=25))
