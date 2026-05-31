from __future__ import annotations

from sqlmodel import Session, select

from app.models.marketplace_listing import MarketplaceListingMapping
from app.schemas.marketplace_listing import MarketplaceListingMappingCreate
from app.schemas.marketplace_publish import MarketplacePublishRequest, MarketplacePublishRequestTarget
from app.schemas.whatnot import WhatnotListingActionResponse
from app.services.marketplace_listing_mappings import create_mapping, update_mapping_status
from app.services.marketplace_listings import LISTING_STATUS_READY_TO_PUBLISH, _owner_listing_or_404
from app.services.marketplace_publish_engine import (
    complete_publish_job,
    create_publish_job,
    mark_target_completed,
    plan_publish_job,
    ready_publish_job,
    rebuild_publish_request,
    validate_job_request,
)
from app.services.marketplace_publish_planner import build_target_payload
from app.services.whatnot_accounts import get_owner_whatnot_account
from app.services.whatnot_connector import WhatnotConnector

LISTING_STATUS_READY = LISTING_STATUS_READY_TO_PUBLISH


def _mapping_for_listing(
    session: Session,
    *,
    owner_id: int,
    listing_id: int,
    marketplace_id: int,
    marketplace_account_id: int,
) -> MarketplaceListingMapping:
    row = session.exec(
        select(MarketplaceListingMapping)
        .where(MarketplaceListingMapping.listing_id == listing_id)
        .where(MarketplaceListingMapping.marketplace_id == marketplace_id)
        .where(MarketplaceListingMapping.marketplace_account_id == marketplace_account_id)
        .order_by(MarketplaceListingMapping.id.asc())
    ).first()
    if row is not None:
        return row
    created = create_mapping(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        payload=MarketplaceListingMappingCreate(
            marketplace_id=marketplace_id,
            marketplace_account_id=marketplace_account_id,
            external_listing_id=None,
            external_url=None,
            sync_status="pending",
        ),
    )
    return session.get(MarketplaceListingMapping, created.id)  # type: ignore[return-value]


def publish_canonical_listing(session: Session, *, owner_id: int, listing_id: int) -> WhatnotListingActionResponse:
    listing = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    if listing.status != LISTING_STATUS_READY:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="Listing must be READY before Whatnot publish.")
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    job = create_publish_job(
        session,
        owner_id=owner_id,
        requested_by=owner_id,
        payload=MarketplacePublishRequest(
            listing_id=listing_id,
            targets=[
                MarketplacePublishRequestTarget(
                    marketplace_id=account.marketplace_id,
                    marketplace_account_id=account.id,
                )
            ],
        ),
    )
    request = rebuild_publish_request(session, owner_id=owner_id, job_id=job.job.id)
    job = validate_job_request(session, owner_id=owner_id, job_id=job.job.id, payload=request)
    if job.job.status == "FAILED":
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Whatnot publish validation failed.")
    job = plan_publish_job(session, owner_id=owner_id, job_id=job.job.id, payload=request)
    job = ready_publish_job(session, owner_id=owner_id, job_id=job.job.id)
    target = job.targets[0]
    payload, _ = build_target_payload(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        marketplace_id=account.marketplace_id,
        marketplace_account_id=account.id,
    )
    payload["canonical_listing"]["listing_id"] = listing_id
    result = connector.publish_listing(session, payload=payload)
    mapping = _mapping_for_listing(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        marketplace_id=account.marketplace_id,
        marketplace_account_id=account.id,
    )
    updated = update_mapping_status(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        mapping_id=int(mapping.id or 0),
        sync_status="mapped",
        external_listing_id=result["external_listing_id"],
        external_url=result["external_url"],
    )
    mark_target_completed(
        session,
        owner_id=owner_id,
        job_id=job.job.id,
        target_id=target.id,
        result_payload_json=result,
    )
    complete_publish_job(session, owner_id=owner_id, job_id=job.job.id)
    return WhatnotListingActionResponse(
        listing_id=listing_id,
        mapping_id=updated.id,
        external_listing_id=updated.external_listing_id,
        external_url=updated.external_url,
        sync_status=updated.sync_status,
        publish_job_id=job.job.id,
    )


def _external_listing_id_for_mapping(session: Session, *, owner_id: int, listing_id: int) -> tuple[MarketplaceListingMapping, str]:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    mapping = session.exec(
        select(MarketplaceListingMapping)
        .where(MarketplaceListingMapping.listing_id == listing_id)
        .where(MarketplaceListingMapping.marketplace_id == account.marketplace_id)
        .where(MarketplaceListingMapping.marketplace_account_id == account.id)
    ).first()
    if mapping is None or not mapping.external_listing_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Whatnot listing mapping not found.")
    return mapping, mapping.external_listing_id


def update_canonical_listing(session: Session, *, owner_id: int, listing_id: int) -> WhatnotListingActionResponse:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    mapping, external_id = _external_listing_id_for_mapping(session, owner_id=owner_id, listing_id=listing_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    payload, _ = build_target_payload(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        marketplace_id=account.marketplace_id,
        marketplace_account_id=account.id,
    )
    result = connector.update_listing(session, external_listing_id=external_id, payload=payload)
    updated = update_mapping_status(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        mapping_id=int(mapping.id or 0),
        sync_status="mapped",
        external_listing_id=result["external_listing_id"],
        external_url=result.get("external_url") or mapping.external_url,
    )
    return WhatnotListingActionResponse(
        listing_id=listing_id,
        mapping_id=updated.id,
        external_listing_id=updated.external_listing_id,
        external_url=updated.external_url,
        sync_status=updated.sync_status,
    )


def pause_listing(session: Session, *, owner_id: int, listing_id: int) -> WhatnotListingActionResponse:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    mapping, external_id = _external_listing_id_for_mapping(session, owner_id=owner_id, listing_id=listing_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    connector.pause_listing(session, external_listing_id=external_id)
    updated = update_mapping_status(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        mapping_id=int(mapping.id or 0),
        sync_status="paused",
    )
    return WhatnotListingActionResponse(
        listing_id=listing_id,
        mapping_id=updated.id,
        external_listing_id=updated.external_listing_id,
        external_url=updated.external_url,
        sync_status=updated.sync_status,
    )


def resume_listing(session: Session, *, owner_id: int, listing_id: int) -> WhatnotListingActionResponse:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    mapping, external_id = _external_listing_id_for_mapping(session, owner_id=owner_id, listing_id=listing_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    connector.resume_listing(session, external_listing_id=external_id)
    updated = update_mapping_status(
        session,
        owner_id=owner_id,
        listing_id=listing_id,
        mapping_id=int(mapping.id or 0),
        sync_status="mapped",
    )
    return WhatnotListingActionResponse(
        listing_id=listing_id,
        mapping_id=updated.id,
        external_listing_id=updated.external_listing_id,
        external_url=updated.external_url,
        sync_status=updated.sync_status,
    )
