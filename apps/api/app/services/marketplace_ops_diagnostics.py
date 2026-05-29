from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlmodel import Session, select

from app.models import (
    LiveSaleQueueItem,
    LiveSaleSession,
    MarketplaceAccount,
    MarketplaceEvent,
    MarketplaceEventProcessingRun,
    MarketplaceInventoryConflict,
    MarketplaceInventorySyncRun,
    MarketplaceListingDraft,
    MarketplaceOffer,
    MarketplaceOrder,
    MarketplacePricingRule,
    MarketplacePriceRecommendation,
    MarketplaceTransaction,
)
from app.models.marketplace_ops_dashboard import MarketplaceOpsDiagnostic
from app.services.live_sale_workflow_service import SESSION_STATUS_LIVE
from app.services.marketplace_event_processing import PROCESSING_STATUS_FAILED
from app.services.marketplace_inventory_sync_service import CONFLICT_STATUS_RESOLVED, SYNC_STATUS_FAILED
from app.services.marketplace_listing_validation import VALIDATION_STATUS_INVALID
from app.services.marketplace_offer_service import OFFER_STATUS_RECEIVED
from app.services.marketplace_order_ingestion import ORDER_STATUS_IMPORTED, TRANSACTION_STATUS_FAILED
from app.services.marketplace_pricing_service import RECOMMENDATION_STATUS_GENERATED


@dataclass(frozen=True)
class MarketplaceOpsDiagnosticResult:
    diagnostic_category: str
    diagnostic_status: str
    diagnostic_code: str
    diagnostic_message: str
    diagnostic_payload_json: dict[str, Any]


DiagnosticBuilder = Callable[[Session, int], MarketplaceOpsDiagnosticResult | None]


def _result(
    *,
    diagnostic_category: str,
    diagnostic_status: str,
    diagnostic_code: str,
    diagnostic_message: str,
    diagnostic_payload_json: dict[str, Any],
) -> MarketplaceOpsDiagnosticResult:
    return MarketplaceOpsDiagnosticResult(
        diagnostic_category=diagnostic_category,
        diagnostic_status=diagnostic_status,
        diagnostic_code=diagnostic_code,
        diagnostic_message=diagnostic_message,
        diagnostic_payload_json=dict(sorted(diagnostic_payload_json.items(), key=lambda pair: str(pair[0]))),
    )


def _no_accounts(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    accounts = session.exec(
        select(MarketplaceAccount.id).where(MarketplaceAccount.organization_id == organization_id).limit(1)
    ).first()
    if accounts is not None:
        return None
    return _result(
        diagnostic_category="account",
        diagnostic_status="error",
        diagnostic_code="no_marketplace_accounts_connected",
        diagnostic_message="No marketplace accounts are connected.",
        diagnostic_payload_json={"connected_accounts": 0},
    )


def _listing_validation_failures(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    invalid = session.exec(
        select(MarketplaceListingDraft)
        .where(MarketplaceListingDraft.organization_id == organization_id)
        .where(MarketplaceListingDraft.validation_status == VALIDATION_STATUS_INVALID)
    ).all()
    if not invalid:
        return None
    return _result(
        diagnostic_category="listing",
        diagnostic_status="warning",
        diagnostic_code="listing_validation_failures_present",
        diagnostic_message="Listing validation failures are present.",
        diagnostic_payload_json={"invalid_listing_drafts": len(invalid)},
    )


def _unresolved_sync_conflicts(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    conflicts = session.exec(
        select(MarketplaceInventoryConflict)
        .where(MarketplaceInventoryConflict.organization_id == organization_id)
        .where(MarketplaceInventoryConflict.conflict_status != CONFLICT_STATUS_RESOLVED)
    ).all()
    if not conflicts:
        return None
    return _result(
        diagnostic_category="sync",
        diagnostic_status="warning",
        diagnostic_code="unresolved_sync_conflicts_present",
        diagnostic_message="Unresolved sync conflicts are present.",
        diagnostic_payload_json={"open_conflicts": len(conflicts)},
    )


def _failed_sync_runs(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    runs = session.exec(
        select(MarketplaceInventorySyncRun)
        .where(MarketplaceInventorySyncRun.organization_id == organization_id)
        .where(MarketplaceInventorySyncRun.sync_status == SYNC_STATUS_FAILED)
    ).all()
    if not runs:
        return None
    return _result(
        diagnostic_category="sync",
        diagnostic_status="error",
        diagnostic_code="failed_sync_runs_present",
        diagnostic_message="Failed sync runs are present.",
        diagnostic_payload_json={"failed_sync_runs": len(runs)},
    )


def _transaction_mismatches(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    failed_transactions = session.exec(
        select(MarketplaceTransaction)
        .where(MarketplaceTransaction.organization_id == organization_id)
        .where(MarketplaceTransaction.transaction_status == TRANSACTION_STATUS_FAILED)
    ).all()
    if not failed_transactions:
        return None
    return _result(
        diagnostic_category="order",
        diagnostic_status="warning",
        diagnostic_code="transaction_mismatches_present",
        diagnostic_message="Transaction mismatches are present.",
        diagnostic_payload_json={
            "failed_transactions": len(failed_transactions),
        },
    )


def _pending_offer_reviews(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    offers = session.exec(
        select(MarketplacePriceRecommendation)
        .where(MarketplacePriceRecommendation.organization_id == organization_id)
        .where(MarketplacePriceRecommendation.recommendation_status == RECOMMENDATION_STATUS_GENERATED)
    ).all()
    offer_rows = session.exec(
        select(MarketplaceOffer)
        .where(MarketplaceOffer.organization_id == organization_id)
        .where(MarketplaceOffer.offer_status == OFFER_STATUS_RECEIVED)
    ).all()
    if not offers and not offer_rows:
        return None
    return _result(
        diagnostic_category="pricing",
        diagnostic_status="warning",
        diagnostic_code="pending_offer_reviews_present",
        diagnostic_message="Pending offer reviews are present.",
        diagnostic_payload_json={"pending_recommendations": len(offers), "received_offers": len(offer_rows)},
    )


def _failed_event_processing_runs(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    runs = session.exec(
        select(MarketplaceEventProcessingRun)
        .where(MarketplaceEventProcessingRun.organization_id == organization_id)
        .where(MarketplaceEventProcessingRun.processing_status == PROCESSING_STATUS_FAILED)
    ).all()
    if not runs:
        return None
    return _result(
        diagnostic_category="event",
        diagnostic_status="error",
        diagnostic_code="failed_event_processing_runs_present",
        diagnostic_message="Failed event processing runs are present.",
        diagnostic_payload_json={"failed_runs": len(runs)},
    )


def _active_live_sale_without_queue_items(session: Session, organization_id: int) -> MarketplaceOpsDiagnosticResult | None:
    sessions = session.exec(
        select(LiveSaleSession).where(LiveSaleSession.organization_id == organization_id).where(LiveSaleSession.session_status == SESSION_STATUS_LIVE)
    ).all()
    if not sessions:
        return None
    empty_sessions = 0
    for live_session in sessions:
        queue_items = session.exec(
            select(LiveSaleQueueItem).where(LiveSaleQueueItem.live_sale_session_id == int(live_session.id or 0))
        ).first()
        if queue_items is None:
            empty_sessions += 1
    if empty_sessions == 0:
        return None
    return _result(
        diagnostic_category="live_sale",
        diagnostic_status="warning",
        diagnostic_code="active_live_sale_without_queue_items",
        diagnostic_message="Active live sale sessions exist without queue items.",
        diagnostic_payload_json={"active_sessions_without_queue_items": empty_sessions},
    )


MARKETPLACE_OPS_DIAGNOSTIC_BUILDERS: tuple[DiagnosticBuilder, ...] = (
    _no_accounts,
    _listing_validation_failures,
    _unresolved_sync_conflicts,
    _failed_sync_runs,
    _transaction_mismatches,
    _pending_offer_reviews,
    _failed_event_processing_runs,
    _active_live_sale_without_queue_items,
)


def evaluate_marketplace_ops_diagnostics(session: Session, organization_id: int) -> list[MarketplaceOpsDiagnosticResult]:
    results: list[MarketplaceOpsDiagnosticResult] = []
    for builder in MARKETPLACE_OPS_DIAGNOSTIC_BUILDERS:
        result = builder(session, organization_id)
        if result is not None:
            results.append(result)
    return results


def summarize_marketplace_ops_diagnostics(rows: list[MarketplaceOpsDiagnostic]) -> dict[str, int]:
    summary = {"ok": 0, "warning": 0, "error": 0}
    for row in rows:
        status = getattr(row, "diagnostic_status", None)
        if status in summary:
            summary[status] += 1
    return summary
