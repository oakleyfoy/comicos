from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.retailer_accounts import (
    MidtownBrowserCaptureResponse,
    MidtownBrowserOrdersResponse,
    MidtownBrowserOrderRead,
    MidtownBrowserSessionResponse,
    MidtownBrowserSessionStatusRead,
)
from app.services.retailer_browser import (
    capture_midtown_browser_order,
    get_midtown_browser_session_status,
    list_midtown_browser_orders,
    start_midtown_browser_session,
)

retailer_browser_v1_router = APIRouter(
    prefix="/api/v1/retailer-browser", tags=["Retailer Browser API v1 (P91-02)"]
)


def attach_retailer_browser_layer(app: FastAPI) -> None:
    app.include_router(retailer_browser_v1_router)


def _status_schema(status) -> MidtownBrowserSessionStatusRead:
    return MidtownBrowserSessionStatusRead(
        retailer=status.retailer,
        account_id=status.account_id,
        status=status.status,
        message=status.message,
        current_url=status.current_url,
        orders_url=status.orders_url,
        authenticated=status.authenticated,
        order_count=status.order_count,
        last_updated_at=status.last_updated_at,
    )


@retailer_browser_v1_router.post("/midtown/session/start", response_model=MidtownBrowserSessionResponse)
def start_midtown_session(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    try:
        status_model = start_midtown_browser_session(session, owner_user_id=int(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


@retailer_browser_v1_router.get("/midtown/session/status", response_model=MidtownBrowserSessionResponse)
def get_midtown_session_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    try:
        status_model = get_midtown_browser_session_status(session, owner_user_id=int(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


@retailer_browser_v1_router.post("/midtown/go-to-orders", response_model=MidtownBrowserOrdersResponse)
def go_to_midtown_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserOrdersResponse:
    assert current_user.id is not None
    try:
        orders_model = list_midtown_browser_orders(session, owner_user_id=int(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MidtownBrowserOrdersResponse(
        session=_status_schema(orders_model.status),
        orders=[MidtownBrowserOrderRead.model_validate(order) for order in orders_model.orders],
    )


@retailer_browser_v1_router.get("/midtown/orders", response_model=MidtownBrowserOrdersResponse)
def get_midtown_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserOrdersResponse:
    assert current_user.id is not None
    try:
        orders_model = list_midtown_browser_orders(session, owner_user_id=int(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MidtownBrowserOrdersResponse(
        session=_status_schema(orders_model.status),
        orders=[MidtownBrowserOrderRead.model_validate(order) for order in orders_model.orders],
    )


@retailer_browser_v1_router.post(
    "/midtown/orders/{retailer_order_number}/capture",
    response_model=MidtownBrowserCaptureResponse,
)
def capture_midtown_order(
    retailer_order_number: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserCaptureResponse:
    assert current_user.id is not None
    try:
        status_model, _, snapshot_id = capture_midtown_browser_order(
            session,
            owner_user_id=int(current_user.id),
            retailer_order_number=retailer_order_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MidtownBrowserCaptureResponse(
        session=_status_schema(status_model),
        order_id=snapshot_id,
        retailer_order_number=retailer_order_number,
    )
