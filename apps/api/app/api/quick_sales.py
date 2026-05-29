"""P44-05 `/api/v1/organizations/*/quick-sales` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, Response, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.quick_sales import (
    QuickSaleCreateRequest,
    QuickSaleLineItemCreateRequest,
    QuickSaleLineItemUpdateRequest,
    QuickSalePaymentCreateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.quick_sale_service import (
    add_quick_sale_line_item,
    complete_quick_sale,
    create_quick_sale,
    get_quick_sale,
    list_quick_sales,
    record_quick_sale_payment,
    update_quick_sale_line_item,
    void_quick_sale,
)

quick_sales_v1_router = APIRouter(prefix="/api/v1", tags=["Quick Sales API v1 (P44-05)"])


def attach_quick_sales_layer(app: FastAPI) -> None:
    app.include_router(quick_sales_v1_router)


@quick_sales_v1_router.get("/organizations/{organization_id}/quick-sales", response_model=ScanApiV1Envelope)
def v1_list_quick_sales(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_quick_sales(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@quick_sales_v1_router.get("/organizations/{organization_id}/quick-sales/{sale_id}", response_model=ScanApiV1Envelope)
def v1_get_quick_sale(
    organization_id: int,
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_quick_sale(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        sale_id=sale_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.sale.id)


@quick_sales_v1_router.post(
    "/organizations/{organization_id}/quick-sales",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_quick_sale(
    organization_id: int,
    payload: QuickSaleCreateRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = create_quick_sale(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.sale.id)


@quick_sales_v1_router.post(
    "/organizations/{organization_id}/quick-sales/{sale_id}/line-items",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_add_quick_sale_line_item(
    organization_id: int,
    sale_id: int,
    payload: QuickSaleLineItemCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = add_quick_sale_line_item(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        sale_id=sale_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.sale.id)


@quick_sales_v1_router.patch(
    "/organizations/{organization_id}/quick-sales/{sale_id}/line-items/{line_item_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_quick_sale_line_item(
    organization_id: int,
    sale_id: int,
    line_item_id: int,
    payload: QuickSaleLineItemUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_quick_sale_line_item(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        sale_id=sale_id,
        line_item_id=line_item_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.sale.id)


@quick_sales_v1_router.post(
    "/organizations/{organization_id}/quick-sales/{sale_id}/payments",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_record_quick_sale_payment(
    organization_id: int,
    sale_id: int,
    payload: QuickSalePaymentCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = record_quick_sale_payment(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        sale_id=sale_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.sale.id)


@quick_sales_v1_router.post(
    "/organizations/{organization_id}/quick-sales/{sale_id}/complete",
    response_model=ScanApiV1Envelope,
)
def v1_complete_quick_sale(
    organization_id: int,
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = complete_quick_sale(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        sale_id=sale_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.sale.id)


@quick_sales_v1_router.post(
    "/organizations/{organization_id}/quick-sales/{sale_id}/void",
    response_model=ScanApiV1Envelope,
)
def v1_void_quick_sale(
    organization_id: int,
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = void_quick_sale(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        sale_id=sale_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.sale.id)
