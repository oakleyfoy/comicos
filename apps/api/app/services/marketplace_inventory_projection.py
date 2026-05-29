from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import (
    MarketplaceInventoryConflict,
    MarketplaceInventoryState,
    MarketplaceInventorySyncRun,
    MarketplaceListingDraft,
)
from app.schemas.marketplace_inventory_sync import MarketplaceInventoryDiagnosticsResponse


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def project_local_inventory_state(_session: Session | None, *, draft: MarketplaceListingDraft | None) -> dict[str, Any]:
    if draft is None:
        return {
            "listing_draft_id": None,
            "inventory_item_id": None,
            "listing_status": "missing",
            "validation_status": "missing",
            "quantity": 0,
            "updated_at": None,
        }
    return _json_safe(
        {
            "listing_draft_id": int(draft.id or 0),
            "inventory_item_id": int(draft.inventory_item_id),
            "listing_status": draft.listing_status,
            "validation_status": draft.validation_status,
            "quantity": int(draft.listing_quantity),
            "updated_at": draft.updated_at,
        }
    )


def project_marketplace_inventory_state(state: MarketplaceInventoryState) -> dict[str, Any]:
    return _json_safe(
        {
            "state_id": int(state.id or 0),
            "marketplace_account_id": int(state.marketplace_account_id),
            "marketplace_listing_draft_id": int(state.marketplace_listing_draft_id),
            "marketplace_listing_identifier": state.marketplace_listing_identifier,
            "inventory_item_id": int(state.inventory_item_id),
            "marketplace_quantity": int(state.marketplace_quantity),
            "sync_status": state.sync_status,
            "last_sync_at": state.last_sync_at,
        }
    )


def generate_marketplace_inventory_snapshot(session: Session, *, state: MarketplaceInventoryState) -> dict[str, Any]:
    draft = session.get(MarketplaceListingDraft, state.marketplace_listing_draft_id)
    return _json_safe(
        {
            "marketplace_listing_identifier": state.marketplace_listing_identifier,
            "local": project_local_inventory_state(session, draft=draft),
            "marketplace": project_marketplace_inventory_state(state),
        }
    )


def generate_sync_diagnostics(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int | None = None,
) -> MarketplaceInventoryDiagnosticsResponse:
    states_query = select(MarketplaceInventoryState).where(MarketplaceInventoryState.organization_id == organization_id)
    conflicts_query = select(MarketplaceInventoryConflict).where(MarketplaceInventoryConflict.organization_id == organization_id)
    runs_query = select(MarketplaceInventorySyncRun).where(MarketplaceInventorySyncRun.organization_id == organization_id)
    if marketplace_account_id is not None:
        states_query = states_query.where(MarketplaceInventoryState.marketplace_account_id == marketplace_account_id)
        runs_query = runs_query.where(MarketplaceInventorySyncRun.marketplace_account_id == marketplace_account_id)
    states = session.exec(states_query).all()
    conflicts = session.exec(conflicts_query).all()
    runs = session.exec(runs_query).all()
    return MarketplaceInventoryDiagnosticsResponse(
        total_states=len(states),
        pending_states=sum(1 for row in states if row.sync_status == "pending"),
        failed_states=sum(1 for row in states if row.sync_status == "failed"),
        active_conflicts=sum(1 for row in conflicts if row.conflict_status != "resolved"),
        completed_runs=sum(1 for row in runs if row.sync_status == "completed"),
        failed_runs=sum(1 for row in runs if row.sync_status == "failed"),
    )
