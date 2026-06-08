"""P90-03 Collector Advisor — aggregate cached intelligence into daily action plans."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.p90_collector_advisor_snapshot import P90CollectorAdvisorSnapshot, utc_now
from app.models.p90_fmv_snapshot import P90FmvSnapshot
from app.schemas.p90_collector_advisor import (
    P90AdvisorActionRead,
    P90AdvisorActivityRead,
    P90AdvisorSignalDiagnosticsRead,
    P90AdvisorTodayActionRead,
    P90CollectorAdvisorBriefingSummary,
    P90CollectorAdvisorDashboardRead,
    P90CollectorAdvisorHistoryRead,
    P90CollectorAdvisorSnapshotRead,
    P90PortfolioImpactRead,
)
from app.services.advisor_priority_service import rank_advisor_actions, rank_mixed_top_actions
from app.services.advisor_proposal_dedupe import count_unique_advisor_actions
from app.services.advisor_proposal_gather import gather_advisor_proposals_with_result
from app.services.automation_engine_service import _Proposal
from app.services.advisor_signal_diagnostics import build_advisor_signal_diagnostics
from app.services.advisor_status import (
    ADVISOR_STATUS_EMPTY_GATHER_FAILED,
    advisor_message_for_status,
    resolve_advisor_dashboard_status,
)
from app.services.collector_alert_priority_service import profit_signal_from_amount, profit_signal_from_discount
from app.services.listing_draft_service import build_listing_draft_briefing
from app.services.portfolio_impact_service import compute_portfolio_impact
from app.services.p90_collector_advisor_notifications import notify_collector_advisor_ready
from app.services.p90_safe_reads import p90_rollback_session

logger = logging.getLogger(__name__)

_PER_CATEGORY = 10


def _comic_from_title(title: str) -> str:
    for prefix in (
        "Strong Buy: ",
        "Buy opportunity: ",
        "Sell now: ",
        "Grade first: ",
        "Collection gap: ",
        "Stale listing: ",
        "Upcoming: ",
        "Portfolio action: ",
    ):
        if title.startswith(prefix):
            return title[len(prefix) :].strip()
    return title.strip()


def _proposal_to_raw(proposal: _Proposal, *, category: str, **extras: Any) -> dict[str, Any]:
    comic = _comic_from_title(proposal.title)
    return {
        "category": category,
        "comic": comic,
        "title": proposal.title,
        "reason": proposal.reason or proposal.summary,
        "summary": proposal.summary,
        "confidence": proposal.confidence,
        "action_route": proposal.action_route,
        "source_system": proposal.source_system,
        "entity_type": proposal.entity_type,
        "entity_id": proposal.entity_id,
        "alert_type": proposal.alert_type,
        "severity": proposal.severity,
        "profit_signal": proposal.profit_signal,
        "urgency_signal": proposal.urgency_signal,
        "marketplace_activity": proposal.marketplace_activity,
        "release_days": proposal.release_days,
        **extras,
    }


def _categorize_proposals(proposals: list[_Proposal]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    buy_raw: list[dict[str, Any]] = []
    sell_raw: list[dict[str, Any]] = []
    grade_raw: list[dict[str, Any]] = []
    watch_raw: list[dict[str, Any]] = []

    for p in proposals:
        if p.alert_type in {"BUY_OPPORTUNITY", "PRICE_DROP"}:
            discount_signal = p.profit_signal
            upside = round(discount_signal * 25.0 * 0.4, 2) if discount_signal else 0.0
            buy_raw.append(
                _proposal_to_raw(
                    p,
                    category="BUY",
                    potential_upside=upside,
                    profit_signal=p.profit_signal,
                )
            )
        elif p.alert_type == "WATCHLIST_MATCH":
            watch_raw.append(_proposal_to_raw(p, category="WATCH", profit_signal=p.profit_signal))
        elif p.alert_type == "SELL_OPPORTUNITY":
            profit = p.profit_signal * 25.0 if p.profit_signal else 0.0
            sell_raw.append(
                _proposal_to_raw(
                    p,
                    category="SELL",
                    profit_potential=round(profit, 2),
                    profit_signal=p.profit_signal,
                )
            )
        elif p.alert_type == "GRADE_OPPORTUNITY":
            gain = p.profit_signal * 25.0 if p.profit_signal else 0.0
            grade_raw.append(
                _proposal_to_raw(
                    p,
                    category="GRADE",
                    value_increase=round(gain, 2),
                    profit_signal=p.profit_signal,
                )
            )
        elif p.alert_type in {"COLLECTION_GAP", "RELEASE_ALERT", "PORTFOLIO_ACTION"}:
            watch_raw.append(_proposal_to_raw(p, category="WATCH", profit_signal=p.profit_signal))

    return buy_raw, sell_raw, grade_raw, watch_raw


def _enrich_buy_from_opportunities(session: Session, *, owner_user_id: int, buy_raw: list[dict]) -> None:
    from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity

    rows = list(
        session.exec(
            select(MarketplaceAcquisitionOpportunity)
            .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
            .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
            .where(MarketplaceAcquisitionOpportunity.recommendation.in_(("STRONG_BUY", "GOOD_BUY")))  # type: ignore[attr-defined]
            .limit(5)
        ).all()
    )
    for row in rows:
        discount = float(row.discount_to_fmv or 0)
        fmv = float(row.estimated_fmv or row.asking_price or 0)
        savings = (fmv * discount / 100.0) if discount and fmv else profit_signal_from_discount(discount) * 25.0 * 0.4
        for item in buy_raw:
            if item.get("entity_type") == "marketplace_acquisition" and item.get("entity_id") == int(row.id or 0):
                item["potential_upside"] = round(savings, 2)
                break


def _fmv_grade_hints(session: Session, *, owner_user_id: int, grade_raw: list[dict]) -> None:
    try:
        rows = list(
            session.exec(
                select(P90FmvSnapshot)
                .where(P90FmvSnapshot.owner_user_id == owner_user_id)
                .where(P90FmvSnapshot.valuation_confidence == "HIGH")
                .where(P90FmvSnapshot.trend_direction == "UP")
                .order_by(P90FmvSnapshot.trend_score.desc())
                .limit(5)
            ).all()
        )
    except Exception:  # noqa: BLE001 — FMV table optional until migrated
        p90_rollback_session(session)
        return
    for row in rows:
        label = f"{row.series} #{row.issue_number}".strip()
        delta = max(0.0, float(row.premium_value) - float(row.market_value))
        if delta <= 0:
            continue
        grade_raw.append(
            {
                "category": "GRADE",
                "comic": label,
                "title": f"FMV uptrend: {label}",
                "reason": f"High-confidence FMV trend {row.trend_direction} ({row.trend_score:.0f})",
                "confidence": row.valuation_confidence,
                "value_increase": round(delta, 2),
                "action_route": "/fmv-intelligence",
                "source_system": "P90_FMV",
                "alert_type": "GRADE_OPPORTUNITY",
                "severity": "MEDIUM",
                "profit_signal": profit_signal_from_amount(delta),
            }
        )


def _finalize_actions(raw: list[dict]) -> list[dict]:
    ranked = rank_advisor_actions(raw, limit=_PER_CATEGORY)
    out: list[dict] = []
    for item in ranked:
        category = str(item.get("category") or "")
        comic = str(item.get("comic") or "")
        out.append(
            {
                "category": category,
                "comic": comic,
                "reason": str(item.get("reason") or ""),
                "confidence": str(item.get("confidence") or "MEDIUM"),
                "priority_score": float(item.get("priority_score") or 0.0),
                "potential_upside": item.get("potential_upside"),
                "profit_potential": item.get("profit_potential"),
                "value_increase": item.get("value_increase"),
                "action_route": str(item.get("action_route") or ""),
                "source_system": str(item.get("source_system") or ""),
                "display_label": f"{category.title()} {comic}".strip(),
                "alert_type": item.get("alert_type"),
                "severity": item.get("severity"),
                "profit_signal": item.get("profit_signal"),
                "urgency_signal": item.get("urgency_signal"),
                "marketplace_activity": item.get("marketplace_activity"),
                "release_days": item.get("release_days"),
                "title": item.get("title"),
                "summary": item.get("summary"),
            }
        )
    return out


def _build_recent_activity(session: Session, *, owner_user_id: int) -> tuple[list[dict], list[dict]]:
    from app.models.p88_marketplace_monitoring import MarketplaceAlert
    from app.services.listing_management_service import build_selling_activity_briefing
    from app.services.p89_market_pricing_service import build_market_pricing_briefing_summary

    activity: list[dict] = []
    alerts: list[dict] = []
    mrows = list(
        session.exec(
            select(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .order_by(MarketplaceAlert.created_at.desc())
            .limit(8)
        ).all()
    )
    for row in mrows:
        entry = {
            "activity_type": row.alert_type or "MARKETPLACE",
            "title": row.title,
            "detail": (row.message or "")[:160],
            "occurred_at": row.created_at.isoformat() if row.created_at else None,
        }
        activity.append(entry)
        if row.status == "NEW":
            alerts.append(entry)

    pricing = build_market_pricing_briefing_summary(session, owner_user_id=owner_user_id)
    if pricing.get("largest_drop"):
        activity.append(
            {
                "activity_type": "PRICE_DROP",
                "title": str(pricing["largest_drop"]),
                "detail": "Market pricing snapshot",
            }
        )
    selling = build_selling_activity_briefing(session, owner_user_id=owner_user_id)
    for key in ("recent_sale", "top_listing"):
        if selling.get(key):
            activity.append(
                {
                    "activity_type": "SELL_ACTIVITY",
                    "title": str(selling[key]),
                    "detail": "Cached selling activity",
                }
            )
    return activity[:12], alerts[:8]


def _extras_for_today(session: Session, *, owner_user_id: int) -> list[dict]:
    extras: list[dict] = []
    try:
        drafts = build_listing_draft_briefing(session, owner_user_id=owner_user_id)
        count = int(drafts.get("drafts_awaiting_review") or 0)
        if count:
            extras.append(
                {
                    "category": "SELL",
                    "comic": f"{count} listing draft{'s' if count != 1 else ''}",
                    "title": f"Review {count} listing draft{'s' if count != 1 else ''}",
                    "reason": "Listing drafts awaiting review",
                    "confidence": "MEDIUM",
                    "action_route": "/listing-drafts",
                    "source_system": "P89_LISTING",
                    "alert_type": "SELL_OPPORTUNITY",
                    "severity": "MEDIUM",
                    "profit_signal": 5.0,
                }
            )
    except Exception:  # noqa: BLE001
        p90_rollback_session(session)
    try:
        from app.services.collection_gaps import list_collection_gaps

        gaps, total = list_collection_gaps(session, owner_user_id=owner_user_id, limit=1, offset=0)
        if total and gaps:
            extras.append(
                {
                    "category": "WATCH",
                    "comic": "collection gap",
                    "title": f"Complete {min(total, 99)} collection gap{'s' if total != 1 else ''}",
                    "reason": gaps[0].rationale or "Missing issues in tracked runs",
                    "confidence": "MEDIUM",
                    "action_route": "/collection-gaps",
                    "source_system": "P55_COLLECTION_GAPS",
                    "alert_type": "COLLECTION_GAP",
                    "severity": "MEDIUM",
                    "profit_signal": 4.0,
                }
            )
    except Exception:  # noqa: BLE001
        p90_rollback_session(session)
    return extras


def _snapshot_to_read(row: P90CollectorAdvisorSnapshot) -> P90CollectorAdvisorSnapshotRead:
    impact = P90PortfolioImpactRead(
        potential_profit=float(row.estimated_profit),
        potential_savings=float(row.estimated_savings),
        potential_value_gain=max(
            0.0,
            float(row.portfolio_score) * 0.0,
        ),
        portfolio_impact_total=float(row.estimated_profit) + float(row.estimated_savings),
        portfolio_score=float(row.portfolio_score),
    )
    meta_gain = sum(float(a.get("value_increase") or 0) for a in row.grade_actions or [])
    impact.potential_value_gain = round(meta_gain, 2)
    impact.portfolio_impact_total = round(
        impact.potential_profit + impact.potential_savings + impact.potential_value_gain, 2
    )

    def _actions(raw: list) -> list[P90AdvisorActionRead]:
        out: list[P90AdvisorActionRead] = []
        for item in raw or []:
            try:
                out.append(P90AdvisorActionRead.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
        return out

    def _today_actions(raw: list) -> list[P90AdvisorTodayActionRead]:
        out: list[P90AdvisorTodayActionRead] = []
        for item in raw or []:
            try:
                out.append(P90AdvisorTodayActionRead.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
        return out

    def _activity_rows(raw: list) -> list[P90AdvisorActivityRead]:
        out: list[P90AdvisorActivityRead] = []
        for item in raw or []:
            try:
                out.append(P90AdvisorActivityRead.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
        return out

    return P90CollectorAdvisorSnapshotRead(
        id=int(row.id or 0),
        snapshot_date=row.snapshot_date,
        buy_actions=_actions(row.buy_actions),
        sell_actions=_actions(row.sell_actions),
        grade_actions=_actions(row.grade_actions),
        watch_actions=_actions(row.watch_actions),
        todays_actions=_today_actions(row.todays_actions),
        recent_activity=_activity_rows(row.recent_activity),
        market_alerts=_activity_rows(row.market_alerts),
        total_actions=int(row.total_actions),
        portfolio_impact=impact,
        created_at=row.created_at,
    )


def generate_collector_advisor_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    day = snapshot_date or date.today()
    gather_result = gather_advisor_proposals_with_result(session, owner_user_id=owner_user_id)
    proposals = gather_result.proposals
    gather_failed = gather_result.all_subsystems_failed
    if gather_result.errors:
        logger.info(
            "advisor gather owner=%s succeeded=%s failed=%s",
            owner_user_id,
            gather_result.succeeded_subsystems,
            gather_result.failed_subsystems,
        )
    buy_raw, sell_raw, grade_raw, watch_raw = _categorize_proposals(proposals)
    try:
        _enrich_buy_from_opportunities(session, owner_user_id=owner_user_id, buy_raw=buy_raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("advisor enrich buy failed owner=%s: %s", owner_user_id, exc)
        p90_rollback_session(session)
    _fmv_grade_hints(session, owner_user_id=owner_user_id, grade_raw=grade_raw)

    buy_actions = _finalize_actions(buy_raw)
    sell_actions = _finalize_actions(sell_raw)
    grade_actions = _finalize_actions(grade_raw)
    watch_actions = _finalize_actions(watch_raw)

    impact = compute_portfolio_impact(
        buy_actions=buy_actions,
        sell_actions=sell_actions,
        grade_actions=grade_actions,
    )

    try:
        extras = _extras_for_today(session, owner_user_id=owner_user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("advisor extras failed owner=%s: %s", owner_user_id, exc)
        p90_rollback_session(session)
        extras = []
    mixed = buy_actions + sell_actions + grade_actions + watch_actions + extras
    todays_actions = rank_mixed_top_actions(mixed, limit=5)
    try:
        recent_activity, market_alerts = _build_recent_activity(session, owner_user_id=owner_user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("advisor recent activity failed owner=%s: %s", owner_user_id, exc)
        p90_rollback_session(session)
        recent_activity, market_alerts = [], []

    total_actions = count_unique_advisor_actions(
        buy_actions,
        sell_actions,
        grade_actions,
        watch_actions,
        todays_actions,
        recent_activity,
        market_alerts,
    )

    summary = {
        "buy_actions": len(buy_actions),
        "sell_actions": len(sell_actions),
        "grade_actions": len(grade_actions),
        "watch_actions": len(watch_actions),
        "estimated_profit": impact["estimated_profit"],
        "estimated_savings": impact["estimated_savings"],
        "total_actions": total_actions,
        "dry_run": dry_run,
    }

    if dry_run:
        summary["gather_failed_subsystems"] = gather_result.failed_subsystems
        summary["gather_errors"] = gather_result.errors
        return summary

    existing = session.exec(
        select(P90CollectorAdvisorSnapshot)
        .where(P90CollectorAdvisorSnapshot.owner_user_id == owner_user_id)
        .where(P90CollectorAdvisorSnapshot.snapshot_date == day)
        .order_by(P90CollectorAdvisorSnapshot.id.desc())
        .limit(1)
    ).first()

    row = existing or P90CollectorAdvisorSnapshot(owner_user_id=owner_user_id, snapshot_date=day)
    row.buy_actions = buy_actions
    row.sell_actions = sell_actions
    row.grade_actions = grade_actions
    row.watch_actions = watch_actions
    row.todays_actions = todays_actions
    row.recent_activity = recent_activity
    row.market_alerts = market_alerts
    row.total_actions = total_actions
    row.estimated_profit = impact["estimated_profit"]
    row.estimated_savings = impact["estimated_savings"]
    row.portfolio_score = impact["portfolio_score"]
    row.generation_status = "GATHER_FAILED" if gather_failed else "OK"
    row.created_at = utc_now()
    session.add(row)
    session.flush()
    try:
        notify_collector_advisor_ready(session, owner_user_id=owner_user_id, snapshot_id=int(row.id or 0))
    except Exception as exc:  # noqa: BLE001
        logger.debug("advisor notification skipped: %s", exc)
    summary["snapshot_id"] = int(row.id or 0)
    summary["gather_failed_subsystems"] = gather_result.failed_subsystems
    summary["gather_errors"] = gather_result.errors
    return summary


def _synthetic_empty_plan_read(*, snapshot_day: date | None = None) -> P90CollectorAdvisorSnapshotRead:
    day = snapshot_day or date.today()
    now = utc_now()
    return P90CollectorAdvisorSnapshotRead(
        id=0,
        snapshot_date=day,
        buy_actions=[],
        sell_actions=[],
        grade_actions=[],
        watch_actions=[],
        todays_actions=[],
        recent_activity=[],
        market_alerts=[],
        total_actions=0,
        portfolio_impact=P90PortfolioImpactRead(),
        created_at=now,
    )


def _persist_empty_advisor_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date | None = None,
    generation_status: str = "GATHER_FAILED",
) -> None:
    day = snapshot_date or date.today()
    existing = session.exec(
        select(P90CollectorAdvisorSnapshot)
        .where(P90CollectorAdvisorSnapshot.owner_user_id == owner_user_id)
        .where(P90CollectorAdvisorSnapshot.snapshot_date == day)
        .order_by(P90CollectorAdvisorSnapshot.id.desc())
        .limit(1)
    ).first()
    row = existing or P90CollectorAdvisorSnapshot(owner_user_id=owner_user_id, snapshot_date=day)
    row.buy_actions = []
    row.sell_actions = []
    row.grade_actions = []
    row.watch_actions = []
    row.todays_actions = []
    row.recent_activity = []
    row.market_alerts = []
    row.total_actions = 0
    row.estimated_profit = 0.0
    row.estimated_savings = 0.0
    row.portfolio_score = 0.0
    row.generation_status = generation_status
    row.created_at = utc_now()
    session.add(row)
    session.flush()


def generate_collector_advisor_dashboard_response(
    session: Session,
    *,
    owner_user_id: int,
    include_diagnostics: bool = False,
) -> P90CollectorAdvisorDashboardRead:
    """Generate advisor plan for UI — always returns HTTP-safe dashboard payload."""
    gather_meta: dict[str, Any] = {}
    try:
        summary = generate_collector_advisor_snapshot(session, owner_user_id=owner_user_id, dry_run=False)
        gather_meta = {
            "gather_errors": summary.get("gather_errors") or [],
            "gather_failed_subsystems": summary.get("gather_failed_subsystems") or [],
        }
        session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("collector advisor generate failed owner=%s: %s", owner_user_id, exc)
        p90_rollback_session(session)
        try:
            _persist_empty_advisor_snapshot(
                session,
                owner_user_id=owner_user_id,
                generation_status="GATHER_FAILED",
            )
            session.commit()
        except Exception as persist_exc:  # noqa: BLE001
            logger.exception("collector advisor empty persist failed owner=%s: %s", owner_user_id, persist_exc)
            p90_rollback_session(session)
            return P90CollectorAdvisorDashboardRead(
                status=ADVISOR_STATUS_EMPTY_GATHER_FAILED,
                plan=_synthetic_empty_plan_read(),
                message=advisor_message_for_status(ADVISOR_STATUS_EMPTY_GATHER_FAILED),
                generated_at=datetime.now(timezone.utc),
            )

    return build_collector_advisor_dashboard(
        session,
        owner_user_id=owner_user_id,
        include_diagnostics=include_diagnostics,
        gather_errors=gather_meta.get("gather_errors"),
        gather_failed_subsystems=gather_meta.get("gather_failed_subsystems"),
    )


def latest_advisor_snapshot(session: Session, *, owner_user_id: int) -> P90CollectorAdvisorSnapshot | None:
    from app.services.p90_safe_reads import p90_safe_call

    return p90_safe_call(
        session,
        lambda: session.exec(
            select(P90CollectorAdvisorSnapshot)
            .where(P90CollectorAdvisorSnapshot.owner_user_id == owner_user_id)
            .order_by(P90CollectorAdvisorSnapshot.snapshot_date.desc(), P90CollectorAdvisorSnapshot.id.desc())
            .limit(1)
        ).first(),
        default=None,
        label="latest_advisor_snapshot",
    )


def build_collector_advisor_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    include_diagnostics: bool = False,
    gather_errors: list[dict[str, Any]] | None = None,
    gather_failed_subsystems: list[str] | None = None,
) -> P90CollectorAdvisorDashboardRead:
    row = latest_advisor_snapshot(session, owner_user_id=owner_user_id)
    now = datetime.now(timezone.utc)
    diagnostics = build_advisor_signal_diagnostics(session, owner_user_id=owner_user_id)
    if include_diagnostics and gather_errors is not None:
        diagnostics = diagnostics.model_copy(
            update={
                "gather_errors": gather_errors,
                "gather_failed_subsystems": gather_failed_subsystems or [],
            }
        )
    if row is None:
        status = resolve_advisor_dashboard_status(
            has_snapshot=False,
            generation_status="",
            total_actions=0,
            diagnostics=diagnostics,
        )
        return P90CollectorAdvisorDashboardRead(
            status=status,
            plan=None,
            message=advisor_message_for_status(status),
            signal_diagnostics=diagnostics if include_diagnostics else None,
            generated_at=now,
        )
    plan = _snapshot_to_read(row)
    total = int(row.total_actions or 0)
    status = resolve_advisor_dashboard_status(
        has_snapshot=True,
        generation_status=str(row.generation_status or ""),
        total_actions=total,
        diagnostics=diagnostics,
    )
    return P90CollectorAdvisorDashboardRead(
        status=status,
        plan=plan,
        message=advisor_message_for_status(status),
        signal_diagnostics=diagnostics if include_diagnostics else None,
        generated_at=now,
    )


def list_advisor_history(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 14,
    offset: int = 0,
) -> P90CollectorAdvisorHistoryRead:
    from sqlalchemy import func

    total = int(
        session.exec(
            select(func.count())
            .select_from(P90CollectorAdvisorSnapshot)
            .where(P90CollectorAdvisorSnapshot.owner_user_id == owner_user_id)
        ).one()
        or 0
    )
    rows = list(
        session.exec(
            select(P90CollectorAdvisorSnapshot)
            .where(P90CollectorAdvisorSnapshot.owner_user_id == owner_user_id)
            .order_by(P90CollectorAdvisorSnapshot.snapshot_date.desc(), P90CollectorAdvisorSnapshot.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return P90CollectorAdvisorHistoryRead(items=[_snapshot_to_read(r) for r in rows], total=total)


def build_collector_advisor_briefing_summary(session: Session, *, owner_user_id: int) -> dict:
    row = latest_advisor_snapshot(session, owner_user_id=owner_user_id)
    if row is None:
        return P90CollectorAdvisorBriefingSummary().model_dump()
    top_buy = (row.buy_actions or [{}])[0] if row.buy_actions else {}
    top_sell = (row.sell_actions or [{}])[0] if row.sell_actions else {}
    top_grade = (row.grade_actions or [{}])[0] if row.grade_actions else {}
    top_watch = (row.watch_actions or [{}])[0] if row.watch_actions else {}
    impact_total = float(row.estimated_profit) + float(row.estimated_savings)
    return P90CollectorAdvisorBriefingSummary(
        top_buy=str(top_buy.get("display_label") or top_buy.get("comic")) if top_buy else None,
        top_sell=str(top_sell.get("display_label") or top_sell.get("comic")) if top_sell else None,
        top_grade=str(top_grade.get("display_label") or top_grade.get("comic")) if top_grade else None,
        top_watch=str(top_watch.get("display_label") or top_watch.get("comic")) if top_watch else None,
        portfolio_impact=round(impact_total, 2),
        total_actions=int(row.total_actions),
    ).model_dump()
