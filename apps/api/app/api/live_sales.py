"""P43-07 `/api/v1/organizations/*/live-sales` routes."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.live_sale_workflows import (
    LiveSaleClaimCreateRequest,
    LiveSaleClaimUpdateRequest,
    LiveSaleQueueItemCreateRequest,
    LiveSaleQueueItemUpdateRequest,
    LiveSaleQueueReorderRequest,
    LiveSaleSessionCreateRequest,
    LiveSaleSessionUpdateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.live_sale_claim_service import (
    create_live_sale_claim,
    list_live_sale_claims,
    update_claim_status,
)
from app.services.live_sale_queue_service import (
    add_item_to_live_sale_queue,
    list_live_sale_queue,
    remove_item_from_live_sale_queue,
    reorder_live_sale_queue,
)
from app.services.live_sale_workflow_service import (
    create_live_sale_session,
    end_live_sale_session,
    get_live_sale_session,
    mark_queue_item_active,
    mark_queue_item_passed,
    mark_queue_item_sold,
    start_live_sale_session,
    update_live_sale_session,
    list_live_sale_sessions,
)

live_sales_v1_router = APIRouter(prefix="/api/v1", tags=["Live Sales API v1 (P43-07)"])


def attach_live_sales_layer(app: FastAPI) -> None:
    app.include_router(live_sales_v1_router)


@live_sales_v1_router.get("/organizations/{organization_id}/live-sales", response_model=ScanApiV1Envelope)
def v1_list_live_sales(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_live_sale_sessions(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@live_sales_v1_router.get("/organizations/{organization_id}/live-sales/{session_id}", response_model=ScanApiV1Envelope)
def v1_get_live_sale_session(
    organization_id: int,
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_live_sale_session(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        session_id=session_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=session_id)


@live_sales_v1_router.get("/organizations/{organization_id}/live-sales/{session_id}/queue", response_model=ScanApiV1Envelope)
def v1_list_live_sale_queue(
    organization_id: int,
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_live_sale_queue(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        live_sale_session_id=session_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@live_sales_v1_router.get("/organizations/{organization_id}/live-sales/{session_id}/claims", response_model=ScanApiV1Envelope)
def v1_list_live_sale_claims(
    organization_id: int,
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_live_sale_claims(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        live_sale_session_id=session_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@live_sales_v1_router.post("/organizations/{organization_id}/live-sales", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_live_sale_session(
    organization_id: int,
    payload: LiveSaleSessionCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_live_sale_session(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.session.id)


@live_sales_v1_router.post("/organizations/{organization_id}/live-sales/{session_id}/start", response_model=ScanApiV1Envelope)
def v1_start_live_sale_session(
    organization_id: int,
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = start_live_sale_session(session, organization_id=organization_id, actor_user_id=int(current_user.id), session_id=session_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.session.id)


@live_sales_v1_router.post("/organizations/{organization_id}/live-sales/{session_id}/end", response_model=ScanApiV1Envelope)
def v1_end_live_sale_session(
    organization_id: int,
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = end_live_sale_session(session, organization_id=organization_id, actor_user_id=int(current_user.id), session_id=session_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.session.id)


@live_sales_v1_router.post("/organizations/{organization_id}/live-sales/{session_id}/queue", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_add_live_sale_queue_item(
    organization_id: int,
    session_id: int,
    payload: LiveSaleQueueItemCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = add_item_to_live_sale_queue(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        live_sale_session_id=session_id,
        inventory_item_id=payload.inventory_item_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        planned_price=payload.planned_price,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@live_sales_v1_router.patch("/organizations/{organization_id}/live-sales/{session_id}", response_model=ScanApiV1Envelope)
def v1_update_live_sale_session(
    organization_id: int,
    session_id: int,
    payload: LiveSaleSessionUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_live_sale_session(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        session_id=session_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.session.id)


@live_sales_v1_router.patch("/organizations/{organization_id}/live-sales/{session_id}/queue/reorder", response_model=ScanApiV1Envelope)
def v1_reorder_live_sale_queue(
    organization_id: int,
    session_id: int,
    payload: LiveSaleQueueReorderRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = reorder_live_sale_queue(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        live_sale_session_id=session_id,
        queue_item_ids=payload.queue_item_ids,
    )
    body = list_live_sale_queue(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        live_sale_session_id=session_id,
        limit=len(items),
        offset=0,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@live_sales_v1_router.patch("/organizations/{organization_id}/live-sales/{session_id}/queue/{queue_item_id}/status", response_model=ScanApiV1Envelope)
def v1_update_live_sale_queue_item_status(
    organization_id: int,
    session_id: int,
    queue_item_id: int,
    payload: LiveSaleQueueItemUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if payload.item_status is None:
        raise ValueError("Queue item status is required.")
    if payload.item_status == "active":
        body = mark_queue_item_active(session, organization_id=organization_id, actor_user_id=int(current_user.id), session_id=session_id, queue_item_id=queue_item_id)
    elif payload.item_status == "sold":
        body = mark_queue_item_sold(
            session,
            organization_id=organization_id,
            actor_user_id=int(current_user.id),
            session_id=session_id,
            queue_item_id=queue_item_id,
            actual_sale_price=payload.actual_sale_price,
        )
    elif payload.item_status == "passed":
        body = mark_queue_item_passed(session, organization_id=organization_id, actor_user_id=int(current_user.id), session_id=session_id, queue_item_id=queue_item_id)
    elif payload.item_status == "removed":
        body = remove_item_from_live_sale_queue(
            session,
            organization_id=organization_id,
            actor_user_id=int(current_user.id),
            live_sale_session_id=session_id,
            queue_item_id=queue_item_id,
        )
    else:
        raise HTTPException(status_code=422, detail="Unsupported live-sale queue item status.")
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.session.id if hasattr(body, "session") else body.id)


@live_sales_v1_router.post("/organizations/{organization_id}/live-sales/{session_id}/claims", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_live_sale_claim(
    organization_id: int,
    session_id: int,
    payload: LiveSaleClaimCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_live_sale_claim(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        live_sale_session_id=session_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@live_sales_v1_router.patch("/organizations/{organization_id}/live-sales/{session_id}/claims/{claim_id}", response_model=ScanApiV1Envelope)
def v1_update_live_sale_claim(
    organization_id: int,
    session_id: int,
    claim_id: int,
    payload: LiveSaleClaimUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_claim_status(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        live_sale_session_id=session_id,
        claim_id=claim_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
