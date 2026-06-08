"""Lightweight SQL counts for Collector Advisor empty-state diagnosis (no heavy builders)."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.collection_gap import CollectionGap
from app.models.exit_candidate import ExitCandidate
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
from app.schemas.p90_collector_advisor import P90AdvisorSignalDiagnosticsRead
from app.services.p90_safe_reads import p90_rollback_session, p90_safe_call


def _count(session: Session, stmt) -> int:
    try:
        return int(session.exec(stmt).one() or 0)
    except Exception:  # noqa: BLE001
        p90_rollback_session(session)
        return 0


def build_advisor_signal_diagnostics(session: Session, *, owner_user_id: int) -> P90AdvisorSignalDiagnosticsRead:
    uid = owner_user_id

    def _build() -> P90AdvisorSignalDiagnosticsRead:
        inventory = _count(
            session,
            select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == uid),
        )
        marketplace_opportunity = _count(
            session,
            select(func.count())
            .select_from(MarketplaceAcquisitionOpportunity)
            .where(MarketplaceAcquisitionOpportunity.owner_user_id == uid)
            .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE"),
        )
        marketplace_alert = _count(
            session,
            select(func.count())
            .select_from(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == uid)
            .where(MarketplaceAlert.status == "NEW"),
        )
        sell_candidate = _count(
            session,
            select(func.count())
            .select_from(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == uid)
            .where(P89SellCandidate.status == "ACTIVE"),
        )
        listing_draft = _count(
            session,
            select(func.count())
            .select_from(P89ListingDraft)
            .where(P89ListingDraft.owner_user_id == uid)
            .where(P89ListingDraft.status == "DRAFT"),
        )
        managed_listing = _count(
            session,
            select(func.count())
            .select_from(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == uid)
            .where(P89ManagedListing.status.in_(("ACTIVE", "EXPIRED", "DRAFT"))),  # type: ignore[attr-defined]
        )
        future_pull = _count(
            session,
            select(func.count())
            .select_from(P81FuturePullListItem)
            .where(P81FuturePullListItem.owner_user_id == uid),
        )
        discovery_alert = _count(
            session,
            select(func.count())
            .select_from(P81DiscoveryAlert)
            .where(P81DiscoveryAlert.owner_user_id == uid)
            .where(P81DiscoveryAlert.status == "ACTIVE"),
        )
        collection_gap = _count(
            session,
            select(func.count())
            .select_from(CollectionGap)
            .where(CollectionGap.owner_user_id == uid),
        )
        automation_alert = _count(
            session,
            select(func.count())
            .select_from(P90CollectorAlert)
            .where(P90CollectorAlert.owner_user_id == uid)
            .where(P90CollectorAlert.status == "NEW"),
        )
        fmv_snapshot = _count(
            session,
            select(func.count()).select_from(P90FmvSnapshot).where(P90FmvSnapshot.owner_user_id == uid),
        )
        grade_before_sell = _count(
            session,
            select(func.count())
            .select_from(GradeBeforeSellRecommendation)
            .where(GradeBeforeSellRecommendation.owner_user_id == uid),
        )
        grading_candidate = _count(
            session,
            select(func.count())
            .select_from(GradingCandidate)
            .where(GradingCandidate.owner_user_id == uid)
            .where(GradingCandidate.status != "ARCHIVED"),
        )
        return P90AdvisorSignalDiagnosticsRead(
            inventory_count=inventory,
            marketplace_opportunity_count=marketplace_opportunity,
            marketplace_alert_count=marketplace_alert,
            sell_candidate_count=sell_candidate,
            listing_draft_count=listing_draft,
            managed_listing_count=managed_listing,
            future_pull_count=future_pull,
            discovery_alert_count=discovery_alert,
            collection_gap_count=collection_gap,
            automation_alert_count=automation_alert,
            fmv_snapshot_count=fmv_snapshot,
            grade_before_sell_count=grade_before_sell,
            grading_candidate_count=grading_candidate,
        )

    return p90_safe_call(
        session,
        _build,
        default=P90AdvisorSignalDiagnosticsRead(),
        label="advisor_signal_diagnostics",
    )


def diagnostics_has_external_signals(diag: P90AdvisorSignalDiagnosticsRead) -> bool:
    return any(
        (
            diag.marketplace_opportunity_count,
            diag.marketplace_alert_count,
            diag.sell_candidate_count,
            diag.listing_draft_count,
            diag.managed_listing_count,
            diag.future_pull_count,
            diag.discovery_alert_count,
            diag.collection_gap_count,
            diag.automation_alert_count,
            diag.fmv_snapshot_count,
            diag.grade_before_sell_count,
            diag.grading_candidate_count,
        )
    )
