"""P90 automation engine — sync collector alerts from cached intelligence (no live engines)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.exit_candidate import ExitCandidate
from app.models.p81_discovery import P81DiscoveryAlert, P81FuturePullListItem
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_monitoring import MarketplaceAlert
from app.models.p89_managed_listing import P89ManagedListing
from app.models.p89_sell_candidate import P89SellCandidate
from app.models.p74_foc_purchase import P74FocAlert, P74FocRecommendationSnapshot
from app.models.p90_collector_alert import P90AutomationRun, P90CollectorAlert, utc_now
from app.services.collector_action_queue_service import count_actions_generated
from app.services.collector_alert_priority_service import (
    PriorityInputs,
    compute_priority_score,
    profit_signal_from_amount,
    profit_signal_from_discount,
    urgency_from_age_days,
)
from app.services.collection_gaps import list_collection_gaps
from app.services.p90_collector_alert_notifications import notify_collector_alert_created

logger = logging.getLogger(__name__)

_PER_TYPE_LIMIT = 40
_STALE_LISTING_DAYS = 30
_PROFIT_SELL_THRESHOLD = 25.0
_ACTIVE_ALERT_STATUS = ("NEW", "ACKNOWLEDGED")


@dataclass
class _Proposal:
    alert_type: str
    severity: str
    title: str
    summary: str
    source_system: str
    entity_type: str
    entity_id: int
    confidence: str
    reason: str
    action_route: str
    profit_signal: float = 0.0
    urgency_signal: float = 0.0
    marketplace_activity: float = 0.0
    release_days: int | None = None


def _severity_from_confidence(confidence: str) -> str:
    c = (confidence or "MEDIUM").upper()
    if c == "HIGH":
        return "HIGH"
    if c == "LOW":
        return "LOW"
    return "MEDIUM"


def _gather_buy_opportunities(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    rows = list(
        session.exec(
            select(MarketplaceAcquisitionOpportunity)
            .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
            .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
            .where(MarketplaceAcquisitionOpportunity.recommendation.in_(("STRONG_BUY", "GOOD_BUY")))  # type: ignore[attr-defined]
            .order_by(MarketplaceAcquisitionOpportunity.opportunity_score.desc())
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    out: list[_Proposal] = []
    for row in rows:
        discount = float(row.discount_to_fmv or 0)
        label = "Strong Buy" if row.recommendation == "STRONG_BUY" else "Buy opportunity"
        reasons = list(row.reasons_json or [])
        rationale = "; ".join(str(r) for r in reasons[:2]) if reasons else ""
        out.append(
            _Proposal(
                alert_type="BUY_OPPORTUNITY",
                severity="HIGH" if row.recommendation == "STRONG_BUY" else "MEDIUM",
                title=f"{label}: {row.title}",
                summary=rationale[:240] if rationale else f"Score {row.opportunity_score:.0f}",
                source_system="P88_MARKETPLACE",
                entity_type="marketplace_acquisition",
                entity_id=int(row.id or 0),
                confidence="HIGH" if row.recommendation == "STRONG_BUY" else "MEDIUM",
                reason=f"{discount:.0f}% below FMV" if discount > 0 else "Cached buy opportunity",
                action_route=f"/marketplace-opportunity/{int(row.id or 0)}",
                profit_signal=profit_signal_from_discount(discount),
                marketplace_activity=min(10.0, float(row.opportunity_score) / 10.0),
            )
        )
    return out


def _gather_marketplace_alerts(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    rows = list(
        session.exec(
            select(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .where(MarketplaceAlert.status == "NEW")
            .order_by(MarketplaceAlert.created_at.desc())
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    out: list[_Proposal] = []
    for row in rows:
        atype = (row.alert_type or "").upper()
        if atype == "PRICE_DROP":
            p90_type = "PRICE_DROP"
        elif atype in {"WATCHLIST_MATCH", "NEW_LISTING"}:
            p90_type = "WATCHLIST_MATCH"
        else:
            p90_type = "BUY_OPPORTUNITY"
        out.append(
            _Proposal(
                alert_type=p90_type,
                severity=row.severity or "MEDIUM",
                title=row.title,
                summary=row.message[:240] if row.message else row.title,
                source_system="P88_MONITORING",
                entity_type="marketplace_alert",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason=row.message[:160] if row.message else "Marketplace monitoring alert",
                action_route="/marketplace-monitoring",
                marketplace_activity=8.0,
                urgency_signal=10.0 if p90_type == "PRICE_DROP" else 5.0,
            )
        )
    return out


def _gather_sell_candidates(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    now = datetime.now(timezone.utc)
    out: list[_Proposal] = []
    rows = list(
        session.exec(
            select(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.status == "ACTIVE")
            .where(P89SellCandidate.recommendation == "SELL_NOW")
            .order_by(P89SellCandidate.sell_score.desc())
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    for row in rows:
        profit = float(row.estimated_profit or 0)
        out.append(
            _Proposal(
                alert_type="SELL_OPPORTUNITY",
                severity="HIGH" if profit >= _PROFIT_SELL_THRESHOLD else "MEDIUM",
                title=f"Sell now: {row.reason_summary[:80] or 'Sell candidate'}",
                summary=row.reason_summary or "Qualifies as Sell Now from cached sell intelligence.",
                source_system="P89_SELL_CANDIDATE",
                entity_type="sell_candidate",
                entity_id=int(row.id or 0),
                confidence=row.confidence,
                reason=row.reason_summary or "SELL_NOW recommendation",
                action_route=f"/sell-candidates?highlight={int(row.id or 0)}",
                profit_signal=profit_signal_from_amount(profit),
                urgency_signal=min(15.0, float(row.sell_score) / 10.0),
            )
        )
    stale_cutoff = now - timedelta(days=_STALE_LISTING_DAYS)
    listings = list(
        session.exec(
            select(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "ACTIVE")
            .where(P89ManagedListing.listed_at.isnot(None))  # type: ignore[union-attr]
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    for row in listings:
        listed = row.listed_at
        if listed is None:
            continue
        if listed.tzinfo is None:
            listed = listed.replace(tzinfo=timezone.utc)
        if listed > stale_cutoff:
            continue
        days = (now - listed).days
        out.append(
            _Proposal(
                alert_type="SELL_OPPORTUNITY",
                severity="MEDIUM",
                title=f"Stale listing: {row.title}",
                summary="Active listing exceeded review threshold — reprice or mark sold.",
                source_system="P89_LISTING_MANAGEMENT",
                entity_type="managed_listing",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason=f"Listed {days} days",
                action_route=f"/listing-management/{int(row.id or 0)}",
                urgency_signal=urgency_from_age_days(days),
            )
        )
    return out


def _gather_grade_candidates(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    rows = list(
        session.exec(
            select(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.status == "ACTIVE")
            .where(P89SellCandidate.recommendation == "GRADE_FIRST")
            .order_by(P89SellCandidate.grade_first_score.desc())
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    out: list[_Proposal] = []
    for row in rows:
        upside = max(0.0, float(row.estimated_sale_value) - float(row.estimated_profit))
        out.append(
            _Proposal(
                alert_type="GRADE_OPPORTUNITY",
                severity="HIGH" if row.confidence == "HIGH" else "MEDIUM",
                title=f"Grade first: {row.reason_summary[:80] or 'Candidate'}",
                summary=row.reason_summary or "May benefit from grading before sale.",
                source_system="P89_SELL_CANDIDATE",
                entity_type="sell_candidate",
                entity_id=int(row.id or 0),
                confidence=row.confidence,
                reason=row.reason_summary or "GRADE_FIRST recommendation",
                action_route="/grade-before-sell",
                profit_signal=profit_signal_from_amount(upside),
            )
        )
    return out


def _gather_collection_gaps(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    gaps, _ = list_collection_gaps(session, owner_user_id=owner_user_id, limit=_PER_TYPE_LIMIT, offset=0)
    out: list[_Proposal] = []
    for gap in gaps:
        title = f"{gap.series_name} #{gap.issue_number}".strip(" #")
        out.append(
            _Proposal(
                alert_type="COLLECTION_GAP",
                severity=gap.priority if gap.priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "MEDIUM",
                title=f"Collection gap: {title or gap.series_name}",
                summary=gap.rationale[:240] if gap.rationale else gap.gap_type.replace("_", " ").title(),
                source_system="P55_COLLECTION_GAPS",
                entity_type="collection_gap",
                entity_id=int(gap.id or 0),
                confidence="HIGH" if gap.priority in {"HIGH", "CRITICAL"} else "MEDIUM",
                reason=gap.rationale[:160] if gap.rationale else "Missing issue in your run",
                action_route="/collection-gaps",
                urgency_signal=12.0 if gap.priority == "CRITICAL" else 6.0,
            )
        )
    return out


def _gather_release_alerts(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
    snap = session.exec(
        select(P74FocRecommendationSnapshot)
        .where(P74FocRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P74FocRecommendationSnapshot.generated_at.desc())
        .limit(1)
    ).first()
    if snap is not None:
        foc_rows = list(
            session.exec(
                select(P74FocAlert)
                .where(P74FocAlert.snapshot_id == int(snap.id or 0))
                .order_by(P74FocAlert.priority_score.desc())
                .limit(20)
            ).all()
        )
        for row in foc_rows:
            out.append(
                _Proposal(
                    alert_type="RELEASE_ALERT",
                    severity="HIGH" if row.priority_score >= 80 else "MEDIUM",
                    title=row.title,
                    summary=row.message[:240] if row.message else "FOC intelligence alert",
                    source_system="P52_PULL_FOC",
                    entity_type="foc_alert",
                    entity_id=int(row.id or 0),
                    confidence="HIGH" if row.priority_score >= 70 else "MEDIUM",
                    reason=row.alert_type.replace("_", " "),
                    action_route="/foc-dashboard",
                    urgency_signal=min(20.0, float(row.priority_score) / 5.0),
                )
            )
    future = list(
        session.exec(
            select(P81FuturePullListItem)
            .where(P81FuturePullListItem.owner_user_id == owner_user_id)
            .order_by(P81FuturePullListItem.personalized_score.desc())
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    today = datetime.now(timezone.utc).date()
    for row in future:
        release_days: int | None = None
        if row.foc_date:
            release_days = (row.foc_date - today).days
        elif row.release_date:
            release_days = (row.release_date - today).days
        if release_days is not None and release_days > 21:
            continue
        out.append(
            _Proposal(
                alert_type="RELEASE_ALERT",
                severity="MEDIUM",
                title=f"Upcoming: {row.title}",
                summary=f"Pipeline {row.pipeline_status} · {row.recommendation_action}",
                source_system="P81_DISCOVERY",
                entity_type="future_pull_item",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason="Release or FOC approaching",
                action_route="/future-pull-list",
                release_days=release_days,
            )
        )
    discovery = list(
        session.exec(
            select(P81DiscoveryAlert)
            .where(P81DiscoveryAlert.owner_user_id == owner_user_id)
            .where(P81DiscoveryAlert.status == "ACTIVE")
            .order_by(P81DiscoveryAlert.updated_at.desc())
            .limit(15)
        ).all()
    )
    for row in discovery:
        out.append(
            _Proposal(
                alert_type="RELEASE_ALERT",
                severity="HIGH" if row.priority in {"CRITICAL", "HIGH"} else "MEDIUM",
                title=row.title,
                summary=row.message[:240] if row.message else "Discovery alert",
                source_system="P81_DISCOVERY",
                entity_type="discovery_alert",
                entity_id=int(row.id or 0),
                confidence="HIGH" if row.priority == "CRITICAL" else "MEDIUM",
                reason=row.alert_type.replace("_", " "),
                action_route="/discovery-dashboard",
                urgency_signal=8.0,
            )
        )
    return out


def _gather_portfolio_actions(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    rows = list(
        session.exec(
            select(ExitCandidate)
            .where(ExitCandidate.owner_user_id == owner_user_id)
            .order_by(ExitCandidate.candidate_score.desc())
            .limit(15)
        ).all()
    )
    out: list[_Proposal] = []
    for row in rows:
        if float(row.candidate_score) < 60:
            continue
        out.append(
            _Proposal(
                alert_type="PORTFOLIO_ACTION",
                severity="MEDIUM",
                title=f"Portfolio action: {row.candidate_reason.replace('_', ' ').title()}",
                summary=f"Unrealized gain ${row.unrealized_gain:.0f} · score {row.candidate_score:.0f}",
                source_system="P54_EXIT",
                entity_type="exit_candidate",
                entity_id=int(row.id or 0),
                confidence="HIGH" if row.confidence_score >= 0.7 else "MEDIUM",
                reason=row.candidate_reason,
                action_route="/exit-dashboard",
                profit_signal=profit_signal_from_amount(float(row.unrealized_gain)),
            )
        )
    return out


def _gather_all_proposals(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    proposals: list[_Proposal] = []
    proposals.extend(_gather_buy_opportunities(session, owner_user_id=owner_user_id))
    proposals.extend(_gather_marketplace_alerts(session, owner_user_id=owner_user_id))
    proposals.extend(_gather_sell_candidates(session, owner_user_id=owner_user_id))
    proposals.extend(_gather_grade_candidates(session, owner_user_id=owner_user_id))
    proposals.extend(_gather_collection_gaps(session, owner_user_id=owner_user_id))
    proposals.extend(_gather_release_alerts(session, owner_user_id=owner_user_id))
    proposals.extend(_gather_portfolio_actions(session, owner_user_id=owner_user_id))
    return proposals


def _proposal_key(p: _Proposal) -> tuple[str, str, int]:
    return (p.alert_type, p.entity_type, p.entity_id)


def _apply_proposal(
    session: Session,
    *,
    owner_user_id: int,
    proposal: _Proposal,
    dry_run: bool,
    stats: dict[str, int],
) -> None:
    priority = compute_priority_score(
        PriorityInputs(
            alert_type=proposal.alert_type,
            severity=proposal.severity,
            confidence=proposal.confidence,
            profit_signal=proposal.profit_signal,
            urgency_signal=proposal.urgency_signal,
            marketplace_activity=proposal.marketplace_activity,
            release_days=proposal.release_days,
        )
    )
    existing = session.exec(
        select(P90CollectorAlert).where(
            P90CollectorAlert.owner_user_id == owner_user_id,
            P90CollectorAlert.alert_type == proposal.alert_type,
            P90CollectorAlert.entity_type == proposal.entity_type,
            P90CollectorAlert.entity_id == proposal.entity_id,
        )
    ).first()
    now = utc_now()
    if existing:
        changed = (
            existing.title != proposal.title
            or existing.summary != proposal.summary
            or abs(existing.priority_score - priority) > 0.5
            or existing.status == "DISMISSED"
            or existing.status == "COMPLETED"
        )
        if not changed:
            return
        if dry_run:
            stats["alerts_updated"] += 1
            return
        existing.title = proposal.title
        existing.summary = proposal.summary
        existing.severity = proposal.severity
        existing.priority_score = priority
        existing.source_system = proposal.source_system
        existing.confidence = proposal.confidence
        existing.reason = proposal.reason
        existing.action_route = proposal.action_route
        existing.updated_at = now
        if existing.status in {"DISMISSED", "COMPLETED"}:
            existing.status = "NEW"
            existing.dismissed_at = None
        session.add(existing)
        stats["alerts_updated"] += 1
        return
    if dry_run:
        stats["alerts_created"] += 1
        return
    row = P90CollectorAlert(
        owner_user_id=owner_user_id,
        alert_type=proposal.alert_type,
        severity=proposal.severity,
        priority_score=priority,
        title=proposal.title,
        summary=proposal.summary,
        source_system=proposal.source_system,
        entity_type=proposal.entity_type,
        entity_id=proposal.entity_id,
        status="NEW",
        confidence=proposal.confidence,
        reason=proposal.reason,
        action_route=proposal.action_route,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    notify_collector_alert_created(session, row=row)
    stats["alerts_created"] += 1


def _dismiss_stale(
    session: Session,
    *,
    owner_user_id: int,
    active_keys: set[tuple[str, str, int]],
    dry_run: bool,
    stats: dict[str, int],
) -> None:
    rows = list(
        session.exec(
            select(P90CollectorAlert)
            .where(P90CollectorAlert.owner_user_id == owner_user_id)
            .where(P90CollectorAlert.status.in_(_ACTIVE_ALERT_STATUS))  # type: ignore[attr-defined]
        ).all()
    )
    for row in rows:
        key = (row.alert_type, row.entity_type, int(row.entity_id))
        if key in active_keys:
            continue
        if dry_run:
            stats["alerts_dismissed"] += 1
            continue
        row.status = "DISMISSED"
        row.dismissed_at = utc_now()
        row.updated_at = utc_now()
        session.add(row)
        stats["alerts_dismissed"] += 1


def run_collector_automation(
    session: Session,
    *,
    owner_user_id: int,
    dry_run: bool = False,
) -> dict:
    """Sync P90 alerts from stored intelligence. Does not invoke pricing, FMV, or marketplace search."""
    started = utc_now()
    stats = {"alerts_created": 0, "alerts_updated": 0, "alerts_dismissed": 0, "actions_generated": 0}
    errors: list[str] = []
    status = "SUCCESS"
    try:
        proposals = _gather_all_proposals(session, owner_user_id=owner_user_id)
        active_keys = {_proposal_key(p) for p in proposals}
        for proposal in proposals:
            _apply_proposal(session, owner_user_id=owner_user_id, proposal=proposal, dry_run=dry_run, stats=stats)
        _dismiss_stale(session, owner_user_id=owner_user_id, active_keys=active_keys, dry_run=dry_run, stats=stats)
        if not dry_run:
            session.flush()
            stats["actions_generated"] = count_actions_generated(session, owner_user_id=owner_user_id)
        else:
            stats["actions_generated"] = min(len(proposals), 10)
    except Exception as exc:  # noqa: BLE001
        status = "FAILED"
        errors.append(str(exc))
        logger.exception("collector automation failed owner=%s", owner_user_id)
    if not dry_run:
        run_row = P90AutomationRun(
            owner_user_id=owner_user_id,
            started_at=started,
            completed_at=utc_now(),
            status="PARTIAL" if errors and status != "FAILED" else status,
            alerts_created=stats["alerts_created"],
            alerts_updated=stats["alerts_updated"],
            alerts_dismissed=stats["alerts_dismissed"],
            errors="; ".join(errors),
        )
        session.add(run_row)
    return {
        **stats,
        "status": status,
        "dry_run": dry_run,
        "errors": errors,
    }
