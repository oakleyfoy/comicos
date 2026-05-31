from __future__ import annotations

from sqlmodel import Session

from app.schemas.marketplace_sync import MarketplaceInventorySyncPlanGenerateRequest
from app.schemas.whatnot import WhatnotInventorySyncResponse
from app.services.marketplace_inventory_availability import get_availability
from app.services.marketplace_inventory_sync_planner import generate_sync_plan
from app.services.marketplace_listing_mappings import update_mapping_status
from app.services.whatnot_accounts import get_owner_whatnot_account
from app.services.whatnot_connector import WhatnotConnector
from app.services.whatnot_listing_publish import _external_listing_id_for_mapping


def sync_listing_quantity(session: Session, *, owner_id: int, listing_id: int) -> WhatnotInventorySyncResponse:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    mapping, external_id = _external_listing_id_for_mapping(session, owner_id=owner_id, listing_id=listing_id)
    availability = get_availability(session, owner_id=owner_id, listing_id=listing_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    connector.sync_inventory(session, external_listing_id=external_id, quantity=availability.available_quantity)
    update_mapping_status(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        mapping_id=int(mapping.id or 0),
        sync_status="mapped",
    )
    return WhatnotInventorySyncResponse(plan_id=None, synced_items=1)


def sync_inventory_plan(session: Session, *, owner_id: int, listing_id: int | None = None) -> WhatnotInventorySyncResponse:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    listing_ids = [listing_id] if listing_id is not None else []
    plan = generate_sync_plan(
        session,
        owner_id=owner_id,
        payload=MarketplaceInventorySyncPlanGenerateRequest(
            listing_ids=listing_ids,
            marketplace_ids=[account.marketplace_id],
        ),
    )
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    synced = 0
    for item in plan.items:
        if item.action_type not in {"UPDATE_QUANTITY", "NOOP"}:
            continue
        if item.action_type == "NOOP":
            continue
        mapping, external_id = _external_listing_id_for_mapping(session, owner_id=owner_id, listing_id=item.listing_id)
        connector.sync_inventory(
            session,
            external_listing_id=external_id,
            quantity=item.target_available_quantity,
        )
        update_mapping_status(
            session,
            owner_id=owner_id,
            listing_id=item.listing_id,
            mapping_id=int(mapping.id or 0),
            sync_status="mapped",
        )
        synced += 1
    return WhatnotInventorySyncResponse(plan_id=plan.plan.id, synced_items=synced)


def sync_availability(session: Session, *, owner_id: int, listing_id: int) -> WhatnotInventorySyncResponse:
    return sync_listing_quantity(session, owner_id=owner_id, listing_id=listing_id)
