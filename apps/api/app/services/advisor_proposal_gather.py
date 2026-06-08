"""Expanded proposal gather for Collector Advisor (cached rows only; no command-center builders)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlmodel import Session, select

from app.models.grade_before_sell import GradeBeforeSellRecommendation
from app.models.grading_candidate import GradingCandidate
from app.models.p81_discovery import P81DiscoveryAlert, P81FuturePullListItem
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_monitoring import MarketplaceAlert
from app.models.p89_listing_draft import P89ListingDraft
from app.models.p89_managed_listing import P89ManagedListing
from app.models.p89_sell_candidate import P89SellCandidate
from app.models.p90_collector_alert import P90CollectorAlert
from app.models.p90_fmv_snapshot import P90FmvSnapshot
from app.services.advisor_gather_logging import log_advisor_gather_failure
from app.services.advisor_proposal_dedupe import dedupe_proposals
from app.services.automation_engine_service import (
    _Proposal,
    _gather_collection_gaps,
    _gather_portfolio_actions,
    _gather_release_alerts,
    _STALE_LISTING_DAYS,
)
from app.services.collector_alert_priority_service import (
    profit_signal_from_amount,
    profit_signal_from_discount,
    urgency_from_age_days,
)
from app.services.p90_safe_reads import p90_rollback_session

logger = logging.getLogger(__name__)

_PER_TYPE_LIMIT = 40
_BUY_RECOMMENDATIONS = ("STRONG_BUY", "GOOD_BUY", "SPEC_BUY", "UNDERVALUED")
_MONITOR_SELL_SCORE = 70.0
_MONITOR_PROFIT_MIN = 15.0


def _gather_buy_opportunities_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    rows = list(
        session.exec(
            select(MarketplaceAcquisitionOpportunity)
            .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
            .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
            .where(MarketplaceAcquisitionOpportunity.recommendation.in_(_BUY_RECOMMENDATIONS))  # type: ignore[attr-defined]
            .order_by(MarketplaceAcquisitionOpportunity.opportunity_score.desc())
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    out: list[_Proposal] = []
    for row in rows:
        discount = float(row.discount_to_fmv or 0)
        label = str(row.recommendation or "Buy").replace("_", " ").title()
        out.append(
            _Proposal(
                alert_type="BUY_OPPORTUNITY",
                severity="HIGH" if row.recommendation == "STRONG_BUY" else "MEDIUM",
                title=f"{label}: {row.title}",
                summary=f"Opportunity score {float(row.opportunity_score):.0f}",
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
    watch_rows = list(
        session.exec(
            select(MarketplaceAcquisitionOpportunity)
            .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
            .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
            .where(MarketplaceAcquisitionOpportunity.recommendation == "WATCH")
            .order_by(MarketplaceAcquisitionOpportunity.opportunity_score.desc())
            .limit(15)
        ).all()
    )
    for row in watch_rows:
        out.append(
            _Proposal(
                alert_type="WATCHLIST_MATCH",
                severity="MEDIUM",
                title=f"Watch: {row.title}",
                summary="Marketplace opportunity on your watch radar",
                source_system="P88_MARKETPLACE",
                entity_type="marketplace_acquisition",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason="WATCH recommendation",
                action_route=f"/marketplace-opportunity/{int(row.id or 0)}",
                profit_signal=profit_signal_from_discount(float(row.discount_to_fmv or 0)),
            )
        )
    return out


def _gather_marketplace_alerts_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
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
        elif atype in {"BELOW_FMV", "UNDERVALUED"}:
            p90_type = "BUY_OPPORTUNITY"
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
                reason=row.message[:160] if row.message else "Marketplace alert",
                action_route="/marketplace-monitoring",
                marketplace_activity=8.0,
                urgency_signal=10.0 if p90_type == "PRICE_DROP" else 5.0,
            )
        )
    return out


def _gather_sell_candidates_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
    for rec in ("SELL_NOW", "MONITOR"):
        rows = list(
            session.exec(
                select(P89SellCandidate)
                .where(P89SellCandidate.owner_user_id == owner_user_id)
                .where(P89SellCandidate.status == "ACTIVE")
                .where(P89SellCandidate.recommendation == rec)
                .order_by(P89SellCandidate.sell_score.desc())
                .limit(_PER_TYPE_LIMIT)
            ).all()
        )
        for row in rows:
            profit = float(row.estimated_profit or 0)
            score = float(row.sell_score or 0)
            if rec == "MONITOR" and profit < _MONITOR_PROFIT_MIN and score < _MONITOR_SELL_SCORE:
                continue
            title_prefix = "Sell now" if rec == "SELL_NOW" else "Monitor sell"
            summary = row.reason_summary or f"{rec} sell candidate"
            out.append(
                _Proposal(
                    alert_type="SELL_OPPORTUNITY",
                    severity="HIGH" if rec == "SELL_NOW" and profit >= 25 else "MEDIUM",
                    title=f"{title_prefix}: {summary[:80]}",
                    summary=summary,
                    source_system="P89_SELL_CANDIDATE",
                    entity_type="sell_candidate",
                    entity_id=int(row.id or 0),
                    confidence=row.confidence,
                    reason=summary,
                    action_route=f"/sell-candidates?highlight={int(row.id or 0)}",
                    profit_signal=profit_signal_from_amount(profit),
                )
            )
    return out


def _gather_managed_listings_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    now = datetime.now(timezone.utc)
    out: list[_Proposal] = []
    stale_cutoff = now - timedelta(days=_STALE_LISTING_DAYS)
    listings = list(
        session.exec(
            select(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "ACTIVE")
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
                title=f"Review stale listing: {row.title}",
                summary="Active listing exceeded review threshold",
                source_system="P89_LISTING_MANAGEMENT",
                entity_type="managed_listing",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason=f"Listed {days} days",
                action_route=f"/listing-management/{int(row.id or 0)}",
                urgency_signal=urgency_from_age_days(days),
            )
        )
    expired = list(
        session.exec(
            select(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "EXPIRED")
            .order_by(P89ManagedListing.updated_at.desc())
            .limit(10)
        ).all()
    )
    for row in expired:
        out.append(
            _Proposal(
                alert_type="SELL_OPPORTUNITY",
                severity="MEDIUM",
                title=f"Review expired listing: {row.title}",
                summary="Re-list, archive, or mark sold",
                source_system="P89_LISTING_MANAGEMENT",
                entity_type="managed_listing",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason="Expired listing needs review",
                action_route=f"/listing-management/{int(row.id or 0)}",
            )
        )
    return out


def _gather_listing_drafts_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
    drafts = list(
        session.exec(
            select(P89ListingDraft)
            .where(P89ListingDraft.owner_user_id == owner_user_id)
            .where(P89ListingDraft.status == "DRAFT")
            .order_by(P89ListingDraft.updated_at.desc())
            .limit(10)
        ).all()
    )
    for row in drafts:
        out.append(
            _Proposal(
                alert_type="SELL_OPPORTUNITY",
                severity="MEDIUM",
                title=f"Review listing draft: {row.title}",
                summary="Listing draft awaiting review",
                source_system="P89_LISTING",
                entity_type="listing_draft",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason="Draft ready for review",
                action_route=f"/listing-drafts/{int(row.id or 0)}",
                profit_signal=5.0,
            )
        )
    return out


def _gather_grade_first_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
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
    for row in rows:
        upside = max(0.0, float(row.estimated_sale_value) - float(row.estimated_profit))
        summary = row.reason_summary or "Grade before sell"
        out.append(
            _Proposal(
                alert_type="GRADE_OPPORTUNITY",
                severity="HIGH" if row.confidence == "HIGH" else "MEDIUM",
                title=f"Grade first: {summary[:80]}",
                summary=summary,
                source_system="P89_SELL_CANDIDATE",
                entity_type="sell_candidate",
                entity_id=int(row.id or 0),
                confidence=row.confidence,
                reason=summary,
                action_route="/grade-before-sell",
                profit_signal=profit_signal_from_amount(upside),
            )
        )
    return out


def _gather_grade_before_sell_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
    gbs_rows = list(
        session.exec(
            select(GradeBeforeSellRecommendation)
            .where(GradeBeforeSellRecommendation.owner_user_id == owner_user_id)
            .where(GradeBeforeSellRecommendation.recommendation == "GRADE_BEFORE_SELL")
            .order_by(GradeBeforeSellRecommendation.created_at.desc())
            .limit(15)
        ).all()
    )
    seen_inv: set[int] = set()
    for row in gbs_rows:
        iid = int(row.inventory_item_id or 0)
        if iid in seen_inv:
            continue
        seen_inv.add(iid)
        gain = float(row.expected_value_gain or 0)
        out.append(
            _Proposal(
                alert_type="GRADE_OPPORTUNITY",
                severity="HIGH" if gain >= 50 else "MEDIUM",
                title="Grade before sell candidate",
                summary=row.rationale[:200] if row.rationale else "Grade-before-sell recommendation",
                source_system="P37_GRADE_BEFORE_SELL",
                entity_type="inventory_copy",
                entity_id=iid,
                confidence="HIGH" if float(row.confidence_score or 0) >= 0.7 else "MEDIUM",
                reason=row.rationale[:160] if row.rationale else "GRADE_BEFORE_SELL",
                action_route="/grade-before-sell",
                profit_signal=profit_signal_from_amount(gain),
            )
        )
    return out


def _gather_grading_candidates_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
    gc_rows = list(
        session.exec(
            select(GradingCandidate)
            .where(GradingCandidate.owner_user_id == owner_user_id)
            .where(GradingCandidate.status != "ARCHIVED")
            .order_by(GradingCandidate.created_at.desc())
            .limit(15)
        ).all()
    )
    for row in gc_rows:
        out.append(
            _Proposal(
                alert_type="GRADE_OPPORTUNITY",
                severity="MEDIUM",
                title=f"Grading queue candidate #{int(row.id or 0)}",
                summary=row.rationale or "Grading pipeline candidate",
                source_system="P37_GRADING_CANDIDATE",
                entity_type="grading_candidate",
                entity_id=int(row.id or 0),
                confidence="MEDIUM",
                reason=row.rationale[:160] if row.rationale else "Grading candidate",
                action_route="/grading-candidates",
            )
        )
    return out


def _gather_fmv_snapshots_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
    fmv_rows = list(
        session.exec(
            select(P90FmvSnapshot)
            .where(P90FmvSnapshot.owner_user_id == owner_user_id)
            .where(P90FmvSnapshot.valuation_confidence == "HIGH")
            .where(P90FmvSnapshot.trend_direction == "UP")
            .order_by(P90FmvSnapshot.trend_score.desc())
            .limit(8)
        ).all()
    )
    for row in fmv_rows:
        label = f"{row.series} #{row.issue_number}".strip()
        delta = max(0.0, float(row.premium_value) - float(row.market_value))
        if delta <= 0:
            continue
        out.append(
            _Proposal(
                alert_type="GRADE_OPPORTUNITY",
                severity="MEDIUM",
                title=f"FMV uptrend: {label}",
                summary=f"High-confidence FMV trend {row.trend_direction}",
                source_system="P90_FMV",
                entity_type="fmv_snapshot",
                entity_id=int(row.id or 0),
                confidence=row.valuation_confidence,
                reason=f"Trend score {float(row.trend_score):.0f}",
                action_route="/fmv-intelligence",
                profit_signal=profit_signal_from_amount(delta),
            )
        )
    return out


def _gather_release_foc_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    return _gather_release_alerts(session, owner_user_id=owner_user_id)


def _gather_future_pull_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
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
                reason="Release or FOC on your pull list",
                action_route="/future-pull-list",
                release_days=release_days,
            )
        )
    return out


def _gather_discovery_alerts_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
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


def _gather_collection_gaps_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    return _gather_collection_gaps(session, owner_user_id=owner_user_id)


def _gather_exit_candidates_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    return _gather_portfolio_actions(session, owner_user_id=owner_user_id)


def _gather_weak_marketplace_watch_advisor(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    out: list[_Proposal] = []
    weak_buy_alerts = list(
        session.exec(
            select(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .where(MarketplaceAlert.status == "NEW")
            .where(MarketplaceAlert.severity.in_(("LOW", "MEDIUM")))  # type: ignore[attr-defined]
            .order_by(MarketplaceAlert.created_at.desc())
            .limit(10)
        ).all()
    )
    for row in weak_buy_alerts:
        atype = (row.alert_type or "").upper()
        if atype in {"PRICE_DROP", "STRONG_BUY"}:
            continue
        out.append(
            _Proposal(
                alert_type="WATCHLIST_MATCH",
                severity=row.severity or "LOW",
                title=row.title,
                summary=row.message[:200] if row.message else "Marketplace watch",
                source_system="P88_MONITORING",
                entity_type="marketplace_alert",
                entity_id=int(row.id or 0),
                confidence="LOW",
                reason=row.message[:120] if row.message else "Watch marketplace activity",
                action_route="/marketplace-monitoring",
            )
        )
    return out


def _map_p90_alert_to_proposal(row: P90CollectorAlert) -> _Proposal:
    atype = (row.alert_type or "").upper()
    alert_type = atype
    if atype == "PRICE_DROP" and (row.severity or "").upper() in {"HIGH", "CRITICAL"}:
        alert_type = "BUY_OPPORTUNITY"
    elif atype == "PRICE_DROP":
        alert_type = "WATCHLIST_MATCH"
    elif atype == "PORTFOLIO_ACTION" and "sell" in (row.summary or "").lower():
        alert_type = "SELL_OPPORTUNITY"
    return _Proposal(
        alert_type=alert_type,
        severity=row.severity or "MEDIUM",
        title=row.title,
        summary=row.summary or row.reason or "",
        source_system=row.source_system or "P90_ALERT",
        entity_type=row.entity_type or "p90_alert",
        entity_id=int(row.entity_id or 0),
        confidence=row.confidence or "MEDIUM",
        reason=row.reason or row.summary or "",
        action_route=row.action_route or "/automation-center",
        profit_signal=float(row.priority_score or 0) / 10.0,
    )


def _gather_p90_collector_alerts(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    rows = list(
        session.exec(
            select(P90CollectorAlert)
            .where(P90CollectorAlert.owner_user_id == owner_user_id)
            .where(P90CollectorAlert.status == "NEW")
            .order_by(P90CollectorAlert.priority_score.desc())
            .limit(_PER_TYPE_LIMIT)
        ).all()
    )
    return [_map_p90_alert_to_proposal(row) for row in rows]


AdvisorGatherFn = Callable[[Session, int], list[_Proposal]]

ADVISOR_GATHER_SUBSYSTEMS: tuple[tuple[str, AdvisorGatherFn], ...] = (
    ("marketplace_opportunities", _gather_buy_opportunities_advisor),
    ("marketplace_alerts", _gather_marketplace_alerts_advisor),
    ("sell_candidates", _gather_sell_candidates_advisor),
    ("managed_listings", _gather_managed_listings_advisor),
    ("listing_drafts", _gather_listing_drafts_advisor),
    ("grade_first_candidates", _gather_grade_first_advisor),
    ("grade_before_sell", _gather_grade_before_sell_advisor),
    ("grading_candidates", _gather_grading_candidates_advisor),
    ("fmv_snapshots", _gather_fmv_snapshots_advisor),
    ("release_foc", _gather_release_foc_advisor),
    ("future_pull_list", _gather_future_pull_advisor),
    ("discovery_alerts", _gather_discovery_alerts_advisor),
    ("collection_gaps", _gather_collection_gaps_advisor),
    ("exit_candidates", _gather_exit_candidates_advisor),
    ("marketplace_watch", _gather_weak_marketplace_watch_advisor),
    ("p90_alerts", _gather_p90_collector_alerts),
)


@dataclass
class AdvisorGatherResult:
    proposals: list[_Proposal] = field(default_factory=list)
    succeeded_subsystems: list[str] = field(default_factory=list)
    failed_subsystems: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def all_subsystems_failed(self) -> bool:
        return bool(self.failed_subsystems) and not self.succeeded_subsystems


def gather_advisor_proposals_with_result(session: Session, *, owner_user_id: int) -> AdvisorGatherResult:
    """Run each advisor source independently; one failure must not poison others."""
    proposals: list[_Proposal] = []
    succeeded: list[str] = []
    failed: list[str] = []
    errors: list[dict[str, Any]] = []
    for subsystem, gather in ADVISOR_GATHER_SUBSYSTEMS:
        try:
            chunk = gather(session, owner_user_id=owner_user_id)
            proposals.extend(chunk)
            succeeded.append(subsystem)
        except Exception as exc:  # noqa: BLE001
            failed.append(subsystem)
            errors.append(log_advisor_gather_failure(subsystem=subsystem, exc=exc))
            p90_rollback_session(session)
    try:
        deduped = dedupe_proposals(proposals)
    except Exception as exc:  # noqa: BLE001
        failed.append("dedupe")
        errors.append(log_advisor_gather_failure(subsystem="dedupe", exc=exc))
        p90_rollback_session(session)
        deduped = proposals
    return AdvisorGatherResult(
        proposals=deduped,
        succeeded_subsystems=succeeded,
        failed_subsystems=failed,
        errors=errors,
    )


def gather_advisor_proposals(session: Session, *, owner_user_id: int) -> list[_Proposal]:
    """Aggregate advisor proposals from cached intelligence; dedupe before return."""
    return gather_advisor_proposals_with_result(session, owner_user_id=owner_user_id).proposals
