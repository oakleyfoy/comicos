from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session

from app.models import MarketplaceInventoryState, MarketplaceListingDraft
from app.schemas.marketplace_inventory_sync import (
    MarketplaceInventoryConflictResponse,
    MarketplaceInventoryDiagnosticsResponse,
    MarketplaceInventoryReconciliationEntryResponse,
    MarketplaceInventoryReconciliationReportResponse,
)
from app.services.marketplace_inventory_projection import (
    generate_sync_diagnostics,
    project_local_inventory_state,
    project_marketplace_inventory_state,
)

CONFLICT_TYPE_QUANTITY_MISMATCH = "quantity_mismatch"
CONFLICT_TYPE_MISSING_LOCAL_INVENTORY = "missing_local_inventory"
CONFLICT_TYPE_MISSING_MARKETPLACE_INVENTORY = "missing_marketplace_inventory"
CONFLICT_TYPE_STALE_MARKETPLACE_STATE = "stale_marketplace_state"
CONFLICT_TYPE_STALE_LOCAL_STATE = "stale_local_state"

CONFLICT_TYPES = (
    CONFLICT_TYPE_MISSING_LOCAL_INVENTORY,
    CONFLICT_TYPE_MISSING_MARKETPLACE_INVENTORY,
    CONFLICT_TYPE_QUANTITY_MISMATCH,
    CONFLICT_TYPE_STALE_MARKETPLACE_STATE,
    CONFLICT_TYPE_STALE_LOCAL_STATE,
)


@dataclass(frozen=True)
class InventoryDifference:
    conflict_type: str
    local_value_json: dict
    marketplace_value_json: dict


def _dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compare_local_vs_marketplace(
    *,
    draft: MarketplaceListingDraft | None,
    state: MarketplaceInventoryState,
) -> tuple[InventoryDifference, ...]:
    differences: list[InventoryDifference] = []
    local_payload = project_local_inventory_state(None, draft=draft)  # type: ignore[arg-type]
    marketplace_payload = project_marketplace_inventory_state(state)

    if draft is None or draft.listing_status == "archived":
        differences.append(
            InventoryDifference(
                conflict_type=CONFLICT_TYPE_MISSING_LOCAL_INVENTORY,
                local_value_json=local_payload,
                marketplace_value_json=marketplace_payload,
            )
        )
        return tuple(differences)

    if state.marketplace_quantity <= 0 and draft.listing_quantity > 0:
        differences.append(
            InventoryDifference(
                conflict_type=CONFLICT_TYPE_MISSING_MARKETPLACE_INVENTORY,
                local_value_json=local_payload,
                marketplace_value_json=marketplace_payload,
            )
        )
    elif draft.listing_quantity != state.marketplace_quantity:
        differences.append(
            InventoryDifference(
                conflict_type=CONFLICT_TYPE_QUANTITY_MISMATCH,
                local_value_json=local_payload,
                marketplace_value_json=marketplace_payload,
            )
        )

    draft_updated_at = _utc(draft.updated_at)
    last_sync_at = _utc(state.last_sync_at)

    if draft_updated_at is not None and last_sync_at is not None and draft_updated_at > last_sync_at:
        differences.append(
            InventoryDifference(
                conflict_type=CONFLICT_TYPE_STALE_MARKETPLACE_STATE,
                local_value_json={"updated_at": _dt(draft_updated_at), "listing_status": draft.listing_status},
                marketplace_value_json={"last_sync_at": _dt(last_sync_at), "sync_status": state.sync_status},
            )
        )
    elif (
        state.marketplace_quantity > 0
        and draft_updated_at is not None
        and last_sync_at is not None
        and draft_updated_at < last_sync_at
        and draft.listing_quantity != state.marketplace_quantity
    ):
        differences.append(
            InventoryDifference(
                conflict_type=CONFLICT_TYPE_STALE_LOCAL_STATE,
                local_value_json={"updated_at": _dt(draft_updated_at), "local_quantity": draft.listing_quantity},
                marketplace_value_json={"last_sync_at": _dt(last_sync_at), "marketplace_quantity": state.marketplace_quantity},
            )
        )

    by_type = {row.conflict_type: row for row in differences}
    return tuple(by_type[key] for key in CONFLICT_TYPES if key in by_type)


def detect_inventory_conflicts(
    session: Session,
    *,
    state: MarketplaceInventoryState,
) -> tuple[InventoryDifference, ...]:
    draft = session.get(MarketplaceListingDraft, state.marketplace_listing_draft_id)
    return compare_local_vs_marketplace(draft=draft, state=state)


def resolve_sync_differences(
    session: Session,
    *,
    state: MarketplaceInventoryState,
) -> tuple[InventoryDifference, ...]:
    return detect_inventory_conflicts(session, state=state)


def reconcile_inventory_state(
    session: Session,
    *,
    state: MarketplaceInventoryState,
) -> tuple[InventoryDifference, ...]:
    return resolve_sync_differences(session, state=state)


def generate_reconciliation_report(
    *,
    diagnostics: MarketplaceInventoryDiagnosticsResponse,
    states: list[MarketplaceInventoryState],
    conflicts: list[MarketplaceInventoryConflictResponse],
) -> MarketplaceInventoryReconciliationReportResponse:
    conflicts_by_state: dict[int, list[str]] = {}
    for conflict in conflicts:
        conflicts_by_state.setdefault(conflict.marketplace_inventory_state_id, []).append(conflict.conflict_type)
    entries = [
        MarketplaceInventoryReconciliationEntryResponse(
            state_id=int(state.id or 0),
            marketplace_listing_identifier=state.marketplace_listing_identifier,
            inventory_item_id=state.inventory_item_id,
            local_quantity=state.local_quantity,
            marketplace_quantity=state.marketplace_quantity,
            conflict_types=sorted(conflicts_by_state.get(int(state.id or 0), [])),
        )
        for state in states
    ]
    entries.sort(key=lambda row: (row.marketplace_listing_identifier, row.state_id))
    return MarketplaceInventoryReconciliationReportResponse(
        diagnostics=diagnostics,
        entries=entries,
        conflicts=conflicts,
    )
