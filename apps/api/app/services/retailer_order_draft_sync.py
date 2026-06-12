"""Build draft imports scoped to a single retailer order snapshot (no cross-order merge)."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models import DraftImport, RetailerAccount, RetailerOrderItemSnapshot, RetailerOrderSnapshot, User
from app.schemas.imports import DraftImportUpdate
from app.services.imports import persist_draft_import, update_import_for_user
from app.services.retailer_sync.retailer_import_enrichment import (
    build_parsed_payload_for_retailer_snapshots,
    retailer_order_import_raw_text,
)

logger = logging.getLogger(__name__)


def _payload_items(draft: DraftImport) -> list[dict]:
    payload = draft.parsed_payload_json or {}
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    return items if isinstance(items, list) else []


def draft_is_dedicated_to_retailer_order(draft: DraftImport, *, retailer_order_number: str) -> bool:
    items = _payload_items(draft)
    if not items:
        return False
    return all(
        isinstance(row, dict) and row.get("retailer_order_number") == retailer_order_number for row in items
    )


def _find_dedicated_draft_import(
    session: Session,
    *,
    owner_user_id: int,
    retailer_order_number: str,
) -> DraftImport | None:
    imports = session.exec(
        select(DraftImport)
        .where(DraftImport.user_id == owner_user_id)
        .order_by(DraftImport.updated_at.desc(), DraftImport.id.desc())
    ).all()
    for draft in imports:
        if draft_is_dedicated_to_retailer_order(draft, retailer_order_number=retailer_order_number):
            return draft
    return None


def list_retailer_order_item_snapshots(
    session: Session,
    *,
    order_snapshot_id: int,
) -> list[RetailerOrderItemSnapshot]:
    return session.exec(
        select(RetailerOrderItemSnapshot)
        .where(RetailerOrderItemSnapshot.retailer_order_snapshot_id == order_snapshot_id)
        .order_by(RetailerOrderItemSnapshot.id.asc())
    ).all()


def sync_isolated_draft_import_for_retailer_order(
    session: Session,
    *,
    account: RetailerAccount,
    order: RetailerOrderSnapshot,
    item_snapshots: list[RetailerOrderItemSnapshot] | None = None,
) -> DraftImport:
    """Replace draft lines with exactly the retailer snapshot rows for this order."""
    owner = session.get(User, account.owner_user_id)
    if owner is None:
        raise ValueError("Retailer account owner not found.")

    if item_snapshots is None:
        item_snapshots = list_retailer_order_item_snapshots(session, order_snapshot_id=int(order.id or 0))
    if not item_snapshots:
        raise ValueError("Retailer order has no line item snapshots.")

    parsed = build_parsed_payload_for_retailer_snapshots(
        retailer=account.retailer,
        order_snapshot=order,
        item_snapshots=item_snapshots,
    )
    raw_text = retailer_order_import_raw_text(order, item_snapshots)

    draft = _find_dedicated_draft_import(
        session,
        owner_user_id=int(account.owner_user_id),
        retailer_order_number=order.retailer_order_number,
    )
    if draft is None or draft.status == "confirmed":
        created = persist_draft_import(
            session,
            current_user=owner,
            raw_text=raw_text,
            parsed=parsed,
        )
        draft_model = session.get(DraftImport, int(created.id))
        if draft_model is None:
            raise ValueError("Draft import was not persisted.")
        logger.info(
            "retailer_draft_sync created isolated draft import_id=%s order=%s lines=%s total_qty=%s",
            draft_model.id,
            order.retailer_order_number,
            len(parsed.items),
            sum(int(item.quantity or 0) for item in parsed.items),
        )
        return draft_model

    updated = update_import_for_user(
        session,
        current_user=owner,
        import_id=int(draft.id),
        payload=DraftImportUpdate(
            raw_text=raw_text,
            parsed_payload_json=parsed,
            confidence_score=parsed.confidence_score,
        ),
    )
    draft_model = session.get(DraftImport, int(updated.id))
    if draft_model is None:
        raise ValueError("Draft import was not updated.")
    logger.info(
        "retailer_draft_sync updated isolated draft import_id=%s order=%s lines=%s total_qty=%s",
        draft_model.id,
        order.retailer_order_number,
        len(parsed.items),
        sum(int(item.quantity or 0) for item in parsed.items),
    )
    return draft_model
