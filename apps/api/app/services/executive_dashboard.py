from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlmodel import Session

from app.schemas.acquisition_dashboard import AcquisitionDashboardItemRead
from app.schemas.daily_action_engine import DailyCollectorActionRead
from app.schemas.executive_dashboard import (
    SECTION_ACQUIRE_TARGETS,
    SECTION_DAILY_ACTIONS,
    SECTION_GRADE_OPPORTUNITIES,
    SECTION_PORTFOLIO_RISK,
    SECTION_PREORDER_THIS_WEEK,
    SECTION_SELL_OPPORTUNITIES,
    SECTION_SYSTEM_HEALTH,
    SECTION_TOP_RECOMMENDATIONS,
    SECTION_WATCH_ITEMS,
    ExecutiveDashboardActionsRead,
    ExecutiveDashboardItemRead,
    ExecutiveDashboardRead,
    ExecutiveDashboardSectionRead,
    ExecutiveDashboardSummaryRead,
)
from app.schemas.recommendation_ranking import (
    RecommendationRankingAuditRead,
    RecommendationRankingDiagnosticsRead,
)
from app.schemas.exit_dashboard import ExitDashboardItemRead
from app.schemas.foc_dashboard import FocDashboardItemRead
from app.services.acquisition_certification import get_latest_acquisition_certification
from app.services.acquisition_dashboard import get_acquisition_dashboard
from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
from app.services.cross_system_recommendation_engine import generate_cross_system_recommendations
from app.services.daily_action_engine import (
    generate_daily_actions,
    get_daily_action_summary,
    list_latest_daily_actions,
)
from app.services.exit_certification import get_latest_exit_certification
from app.services.exit_dashboard import get_exit_dashboard
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import utc_today
from app.services.portfolio_certification import build_portfolio_certification_ops_panel
from app.services.production_readiness import validate_production_readiness
from app.services.purchase_budgets import build_purchase_budget_summary
from app.services.recommendation_ranking_diagnostics import (
    build_recommendation_ranking_audit,
    diagnostics_from_audit,
)

TOP_N = 12
ACTIONS_LIMIT = 25

SECTION_META: dict[str, tuple[str, str]] = {
    SECTION_DAILY_ACTIONS: ("Today's Top Actions", "No daily actions queued yet."),
    SECTION_TOP_RECOMMENDATIONS: (
        "Top Recommendations",
        "No forward recommendations in the next 90 days yet. Import release catalog and refresh intelligence.",
    ),
    SECTION_PREORDER_THIS_WEEK: ("Preorder This Week", "No urgent preorder actions."),
    SECTION_ACQUIRE_TARGETS: ("Acquisition Targets", "No acquisition targets found."),
    SECTION_GRADE_OPPORTUNITIES: ("Grade Opportunities", "No grading opportunities right now."),
    SECTION_SELL_OPPORTUNITIES: ("Sell Opportunities", "No sell recommendations."),
    SECTION_PORTFOLIO_RISK: ("Portfolio Risk", "No portfolio risk warnings."),
    SECTION_WATCH_ITEMS: ("Watch / Review", "No watch or review items."),
    SECTION_SYSTEM_HEALTH: ("System Health", "No certification or health indicators available yet."),
}


@dataclass(frozen=True)
class _Sortable:
    payload: ExecutiveDashboardItemRead
    primary: float
    confidence: float
    due_ord: int
    value: float
    created_at: datetime
    item_id: int


def _parse_created_at(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.fromisoformat("1970-01-01T00:00:00+00:00")
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.fromisoformat("1970-01-01T00:00:00+00:00")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromisoformat("1970-01-01T00:00:00+00:00")


def _due_ord(d: date | None) -> int:
    return d.toordinal() if d is not None else 999999


def _priority_for_sort(item: ExecutiveDashboardItemRead) -> float:
    if item.priority_score is not None:
        return float(item.priority_score)
    return 0.0


def _sort_key(row: _Sortable) -> tuple:
    return (
        -row.primary,
        -row.confidence,
        row.due_ord,
        -row.value,
        row.created_at.isoformat(),
        row.item_id,
    )


def _sort_top_recommendations(
    items: list[ExecutiveDashboardItemRead],
    *,
    limit: int = TOP_N,
) -> list[ExecutiveDashboardItemRead]:
    """Rank Top Recommendations strictly by stored priority score (not title)."""
    ordered = sorted(
        items,
        key=lambda item: (
            -_priority_for_sort(item),
            -(float(item.confidence_score or 0.0)),
            -(float(item.estimated_value or 0.0)),
            item.item_id,
        ),
    )[:limit]
    ranked: list[ExecutiveDashboardItemRead] = []
    for display_rank, item in enumerate(ordered, start=1):
        ranked.append(item.model_copy(update={"recommendation_rank": display_rank}))
    return ranked


def _sort_and_trim(items: list[ExecutiveDashboardItemRead], *, limit: int = TOP_N) -> list[ExecutiveDashboardItemRead]:
    sortable: list[_Sortable] = []
    for item in items:
        sortable.append(
            _Sortable(
                payload=item,
                primary=_priority_for_sort(item),
                confidence=float(item.confidence_score or 0),
                due_ord=_due_ord(item.due_date),
                value=float(item.estimated_value or 0),
                created_at=_parse_created_at(item.created_at),
                item_id=item.item_id,
            )
        )
    return [r.payload for r in sorted(sortable, key=_sort_key)[:limit]]


def _section_read(
    section: str,
    items: list[ExecutiveDashboardItemRead],
    *,
    ranking_diagnostics: RecommendationRankingDiagnosticsRead | None = None,
) -> ExecutiveDashboardSectionRead:
    title, empty_message = SECTION_META[section]
    if section == SECTION_TOP_RECOMMENDATIONS:
        trimmed = _sort_top_recommendations(items)
    else:
        trimmed = _sort_and_trim(items)
    return ExecutiveDashboardSectionRead(
        section=section,
        title=title,
        empty_message=empty_message,
        items=trimmed,
        ranking_diagnostics=ranking_diagnostics if section == SECTION_TOP_RECOMMENDATIONS else None,
    )


def _matches_filters(
    item: ExecutiveDashboardItemRead,
    *,
    section: str | None,
    recommendation_type: str | None,
    action_type: str | None,
    priority_min: float | None,
    publisher: str | None,
) -> bool:
    if section and item.section != section.strip().upper():
        return False
    if recommendation_type:
        rec = (item.recommendation_type or "").upper()
        if rec != recommendation_type.strip().upper():
            return False
    if action_type:
        act = (item.action_type or item.recommendation_type or "").upper()
        if act != action_type.strip().upper():
            return False
    if priority_min is not None and float(item.priority_score or 0) < float(priority_min):
        return False
    if publisher:
        needle = publisher.strip().lower()
        if needle not in item.publisher.lower() and needle not in item.title.lower():
            return False
    return True


def _filter_items(
    items: list[ExecutiveDashboardItemRead],
    *,
    section: str | None,
    recommendation_type: str | None,
    action_type: str | None,
    priority_min: float | None,
    publisher: str | None,
) -> list[ExecutiveDashboardItemRead]:
    if not any([section, recommendation_type, action_type, priority_min, publisher]):
        return items
    return [
        item
        for item in items
        if _matches_filters(
            item,
            section=section,
            recommendation_type=recommendation_type,
            action_type=action_type,
            priority_min=priority_min,
            publisher=publisher,
        )
    ]


def _from_daily(row: DailyCollectorActionRead) -> ExecutiveDashboardItemRead:
    created = row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else str(row.created_at)
    return ExecutiveDashboardItemRead(
        section=SECTION_DAILY_ACTIONS,
        item_type="daily_action",
        item_id=row.id,
        title=row.title,
        action_type=row.action_type,
        recommendation_type=row.action_type,
        priority_score=row.priority_score,
        confidence_score=row.confidence_score,
        due_date=row.due_date,
        rationale=row.rationale,
        source_systems=list(row.source_systems or []),
        created_at=created,
    )


def _from_cross(row) -> ExecutiveDashboardItemRead:
    created = row.created_at.isoformat() if hasattr(row.created_at, "isoformat") else str(row.created_at)
    return ExecutiveDashboardItemRead(
        section=SECTION_TOP_RECOMMENDATIONS,
        item_type="cross_system_recommendation",
        item_id=row.id,
        title=row.title,
        recommendation_type=row.recommendation_type,
        priority_score=row.priority_score,
        confidence_score=row.confidence_score,
        recommendation_rank=row.recommendation_rank,
        estimated_value=row.estimated_value,
        rationale=row.rationale,
        source_systems=list(row.source_systems or []),
        created_at=created,
    )


def _from_foc(item: FocDashboardItemRead) -> ExecutiveDashboardItemRead:
    days = item.days_until_foc if item.days_until_foc is not None else 14
    priority = max(50.0, min(100.0, 100.0 - float(days) * 2.0))
    return ExecutiveDashboardItemRead(
        section=SECTION_PREORDER_THIS_WEEK,
        item_type="foc_release",
        item_id=item.release_id,
        title=item.title or f"{item.series_name} #{item.issue_number}".strip(),
        publisher=item.publisher,
        recommendation_type="PREORDER",
        action_type="PREORDER",
        priority_score=round(priority, 1),
        confidence_score=item.confidence_score,
        due_date=item.foc_date,
        rationale="; ".join(item.reasons) if item.reasons else "FOC window requires pull list action.",
        created_at="",
    )


def _from_acquisition(item: AcquisitionDashboardItemRead) -> ExecutiveDashboardItemRead:
    return ExecutiveDashboardItemRead(
        section=SECTION_ACQUIRE_TARGETS,
        item_type=item.item_type,
        item_id=item.item_id,
        title=item.title,
        publisher=item.publisher,
        recommendation_type=(item.recommendation or "ACQUIRE").upper(),
        action_type="ACQUIRE",
        priority_score=item.priority_score,
        confidence_score=item.confidence_score,
        estimated_value=item.total_price or item.target_price,
        rationale=item.rationale or "",
        created_at=item.created_at,
    )


def _from_exit(item: ExitDashboardItemRead, *, section: str) -> ExecutiveDashboardItemRead:
    rec = (item.recommendation or item.action or "").upper()
    return ExecutiveDashboardItemRead(
        section=section,
        item_type=item.item_type,
        item_id=item.item_id,
        title=item.title,
        publisher=item.publisher,
        recommendation_type=rec or None,
        action_type=rec or None,
        priority_score=item.priority_score,
        confidence_score=item.confidence_score,
        estimated_value=item.capital_value,
        rationale=item.rationale,
        created_at=item.created_at,
    )


def _as_created_at(value: datetime | str | None) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_system_health(session: Session, *, owner_user_id: int) -> list[ExecutiveDashboardItemRead]:
    items: list[ExecutiveDashboardItemRead] = []
    portfolio = build_portfolio_certification_ops_panel(session, owner_user_id=owner_user_id)
    if portfolio.last_certification_at:
        items.append(
            ExecutiveDashboardItemRead(
                section=SECTION_SYSTEM_HEALTH,
                item_type="portfolio_certification",
                item_id=1,
                title="Portfolio certification",
                priority_score=float(portfolio.readiness_score or 0),
                confidence_score=1.0,
                health_status=portfolio.validation_status or portfolio.certification_result,
                rationale=f"Latest portfolio certification result: {portfolio.certification_result or 'UNKNOWN'}.",
                created_at=portfolio.last_certification_at.isoformat()
                if hasattr(portfolio.last_certification_at, "isoformat")
                else str(portfolio.last_certification_at),
            )
        )
    acq_cert = get_latest_acquisition_certification(session, owner_user_id=owner_user_id)
    if acq_cert is not None:
        acq_health = getattr(acq_cert.report, "health_status", None) or acq_cert.validation_status
        items.append(
            ExecutiveDashboardItemRead(
                section=SECTION_SYSTEM_HEALTH,
                item_type="acquisition_certification",
                item_id=2,
                title="Acquisition certification",
                priority_score=float(acq_cert.readiness_score or 0),
                confidence_score=1.0,
                health_status=acq_health,
                rationale=f"Acquisition stack validation: {acq_cert.validation_status}.",
                created_at=_as_created_at(acq_cert.completed_at or acq_cert.started_at),
            )
        )
    exit_cert = get_latest_exit_certification(session, owner_user_id=owner_user_id)
    if exit_cert is not None:
        exit_health = getattr(exit_cert.report, "health_status", None) or exit_cert.validation_status
        items.append(
            ExecutiveDashboardItemRead(
                section=SECTION_SYSTEM_HEALTH,
                item_type="exit_certification",
                item_id=3,
                title="Exit certification",
                priority_score=float(exit_cert.readiness_score or 0),
                confidence_score=1.0,
                health_status=exit_health,
                rationale=f"Exit intelligence validation: {exit_cert.validation_status}.",
                created_at=_as_created_at(exit_cert.completed_at or exit_cert.started_at),
            )
        )
    readiness = validate_production_readiness(session, owner_user_id=owner_user_id)
    if readiness:
        passed = sum(1 for c in readiness if c.check_status == "PASS")
        failed = sum(1 for c in readiness if c.check_status == "FAIL")
        status = "HEALTHY" if failed == 0 else "ATTENTION"
        items.append(
            ExecutiveDashboardItemRead(
                section=SECTION_SYSTEM_HEALTH,
                item_type="production_readiness",
                item_id=4,
                title="Production readiness",
                priority_score=round(passed / max(len(readiness), 1) * 100.0, 1),
                confidence_score=1.0,
                health_status=status,
                rationale=f"{passed} passed, {failed} failed of {len(readiness)} readiness checks.",
                created_at="",
            )
        )
    return items


def _collect_raw_sections(session: Session, *, owner_user_id: int) -> dict[str, list[ExecutiveDashboardItemRead]]:
    generate_daily_actions(session, owner_user_id=owner_user_id)
    generate_cross_system_recommendations(session, owner_user_id=owner_user_id)

    daily_rows, _ = list_latest_daily_actions(session, owner_user_id=owner_user_id, limit=200, offset=0)
    cross_rows, _ = list_latest_cross_system_recommendations(session, owner_user_id=owner_user_id, limit=200, offset=0)

    foc = get_foc_dashboard(session, owner_user_id=owner_user_id, today=utc_today())
    week_end = utc_today() + timedelta(days=7)
    preorder_items: list[ExecutiveDashboardItemRead] = []
    for src in foc.action_required + foc.upcoming_foc:
        if src.foc_date is not None and src.foc_date <= week_end:
            preorder_items.append(_from_foc(src))

    acq = get_acquisition_dashboard(session, owner_user_id=owner_user_id)
    acquire_items: list[ExecutiveDashboardItemRead] = []
    for src in acq.top_opportunities + acq.top_collection_gaps + acq.below_target_price + acq.marketplace_candidates:
        acquire_items.append(_from_acquisition(src))

    exit_dash = get_exit_dashboard(session, owner_user_id=owner_user_id)
    grade_items = [_from_exit(i, section=SECTION_GRADE_OPPORTUNITIES) for i in exit_dash.top_grade_before_sell]
    sell_items = [_from_exit(i, section=SECTION_SELL_OPPORTUNITIES) for i in exit_dash.top_sell_recommendations]
    risk_items = [_from_exit(i, section=SECTION_PORTFOLIO_RISK) for i in exit_dash.top_rebalance_actions]

    watch_items: list[ExecutiveDashboardItemRead] = []
    for row in daily_rows:
        if row.action_type in {"WATCH", "REVIEW"}:
            watch_items.append(_from_daily(row))
    for src in exit_dash.review_required:
        item = _from_exit(src, section=SECTION_WATCH_ITEMS)
        item.recommendation_type = "REVIEW"
        item.action_type = "REVIEW"
        watch_items.append(item)
    for src in acq.review_required:
        item = _from_acquisition(src)
        item.section = SECTION_WATCH_ITEMS
        item.action_type = "REVIEW"
        watch_items.append(item)
    for src in foc.watchlist:
        watch_items.append(_from_foc(src))

    return {
        SECTION_DAILY_ACTIONS: [_from_daily(r) for r in daily_rows],
        SECTION_TOP_RECOMMENDATIONS: [_from_cross(r) for r in cross_rows],
        SECTION_PREORDER_THIS_WEEK: preorder_items,
        SECTION_ACQUIRE_TARGETS: acquire_items,
        SECTION_GRADE_OPPORTUNITIES: grade_items,
        SECTION_SELL_OPPORTUNITIES: sell_items,
        SECTION_PORTFOLIO_RISK: risk_items,
        SECTION_WATCH_ITEMS: watch_items,
        SECTION_SYSTEM_HEALTH: _build_system_health(session, owner_user_id=owner_user_id),
    }


def _build_summary(
    session: Session,
    *,
    owner_user_id: int,
    sections: dict[str, list[ExecutiveDashboardItemRead]],
) -> ExecutiveDashboardSummaryRead:
    daily_summary = get_daily_action_summary(session, owner_user_id=owner_user_id)
    exit_dash = get_exit_dashboard(session, owner_user_id=owner_user_id)
    acq = get_acquisition_dashboard(session, owner_user_id=owner_user_id)
    budget = build_purchase_budget_summary(session, owner_user_id=owner_user_id)
    top_recs = [i for i in sections[SECTION_TOP_RECOMMENDATIONS] if (i.recommendation_rank or 99) <= 5]
    return ExecutiveDashboardSummaryRead(
        total_daily_actions=daily_summary.total_actions,
        critical_daily_actions=daily_summary.critical_actions,
        top_recommendations_count=len(top_recs),
        preorder_action_count=daily_summary.preorder_actions + len(sections[SECTION_PREORDER_THIS_WEEK]),
        acquisition_target_count=len(sections[SECTION_ACQUIRE_TARGETS])
        or acq.summary.open_collection_gaps + acq.summary.high_priority_opportunities,
        grading_opportunity_count=exit_dash.summary.grade_before_sell_recommendations,
        sell_opportunity_count=exit_dash.summary.sell_recommendations,
        rebalance_warning_count=exit_dash.summary.rebalance_actions,
        review_required_count=exit_dash.summary.review_required_count + acq.summary.review_required_candidates,
        estimated_capital_recovery=exit_dash.summary.estimated_capital_recovery,
        budget_remaining=budget.remaining_budget if budget.is_active else None,
    )


def get_executive_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    section: str | None = None,
    recommendation_type: str | None = None,
    action_type: str | None = None,
    priority_min: float | None = None,
    publisher: str | None = None,
) -> ExecutiveDashboardRead:
    raw = _collect_raw_sections(session, owner_user_id=owner_user_id)
    filtered = {
        key: _filter_items(
            items,
            section=section,
            recommendation_type=recommendation_type,
            action_type=action_type,
            priority_min=priority_min,
            publisher=publisher,
        )
        for key, items in raw.items()
    }
    summary = _build_summary(session, owner_user_id=owner_user_id, sections=raw)
    ranking_audit = build_recommendation_ranking_audit(
        session,
        owner_user_id=owner_user_id,
        limit=100,
        refresh=False,
    )
    ranking_diag = diagnostics_from_audit(ranking_audit)
    return ExecutiveDashboardRead(
        summary=summary,
        daily_actions=_section_read(SECTION_DAILY_ACTIONS, filtered[SECTION_DAILY_ACTIONS]),
        top_recommendations=_section_read(
            SECTION_TOP_RECOMMENDATIONS,
            filtered[SECTION_TOP_RECOMMENDATIONS],
            ranking_diagnostics=ranking_diag,
        ),
        preorder_this_week=_section_read(SECTION_PREORDER_THIS_WEEK, filtered[SECTION_PREORDER_THIS_WEEK]),
        acquire_targets=_section_read(SECTION_ACQUIRE_TARGETS, filtered[SECTION_ACQUIRE_TARGETS]),
        grade_opportunities=_section_read(SECTION_GRADE_OPPORTUNITIES, filtered[SECTION_GRADE_OPPORTUNITIES]),
        sell_opportunities=_section_read(SECTION_SELL_OPPORTUNITIES, filtered[SECTION_SELL_OPPORTUNITIES]),
        portfolio_risk=_section_read(SECTION_PORTFOLIO_RISK, filtered[SECTION_PORTFOLIO_RISK]),
        watch_items=_section_read(SECTION_WATCH_ITEMS, filtered[SECTION_WATCH_ITEMS]),
        system_health=_section_read(SECTION_SYSTEM_HEALTH, filtered[SECTION_SYSTEM_HEALTH]),
    )


def get_executive_dashboard_summary(
    session: Session,
    *,
    owner_user_id: int,
    section: str | None = None,
    recommendation_type: str | None = None,
    action_type: str | None = None,
    priority_min: float | None = None,
    publisher: str | None = None,
) -> ExecutiveDashboardSummaryRead:
    raw = _collect_raw_sections(session, owner_user_id=owner_user_id)
    if any([section, recommendation_type, action_type, priority_min, publisher]):
        raw = {
            key: _filter_items(
                items,
                section=section,
                recommendation_type=recommendation_type,
                action_type=action_type,
                priority_min=priority_min,
                publisher=publisher,
            )
            for key, items in raw.items()
        }
    return _build_summary(session, owner_user_id=owner_user_id, sections=raw)


def get_executive_dashboard_ranking_audit(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
) -> RecommendationRankingAuditRead:
    return build_recommendation_ranking_audit(
        session,
        owner_user_id=owner_user_id,
        limit=limit,
        refresh=True,
    )


def get_executive_dashboard_actions(
    session: Session,
    *,
    owner_user_id: int,
    section: str | None = None,
    recommendation_type: str | None = None,
    action_type: str | None = None,
    priority_min: float | None = None,
    publisher: str | None = None,
) -> ExecutiveDashboardActionsRead:
    dashboard = get_executive_dashboard(
        session,
        owner_user_id=owner_user_id,
        section=section,
        recommendation_type=recommendation_type,
        action_type=action_type,
        priority_min=priority_min,
        publisher=publisher,
    )
    urgent: list[ExecutiveDashboardItemRead] = []
    urgent.extend(dashboard.daily_actions.items)
    urgent.extend(dashboard.top_recommendations.items[:5])
    urgent.extend(dashboard.preorder_this_week.items[:5])
    urgent.extend(dashboard.acquire_targets.items[:5])
    urgent.extend(dashboard.grade_opportunities.items[:5])
    urgent.extend(dashboard.sell_opportunities.items[:5])
    urgent.extend(dashboard.portfolio_risk.items[:5])

    seen: set[tuple[str, int]] = set()
    deduped: list[ExecutiveDashboardItemRead] = []
    for item in urgent:
        key = (item.item_type, item.item_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return ExecutiveDashboardActionsRead(priority_actions=_sort_and_trim(deduped, limit=ACTIONS_LIMIT))
