from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.retailer_accounts import (
    MidtownBrowserClickRequest,
    MidtownBrowserCaptureResponse,
    MidtownBrowserFrameResponse,
    MidtownBrowserOrdersResponse,
    MidtownBrowserOrderRead,
    MidtownBrowserKeyRequest,
    MidtownBrowserSessionResponse,
    MidtownBrowserSessionStatusRead,
    MidtownBrowserTypeRequest,
)
from app.services.retailer_browser import (
    capture_midtown_browser_order,
    click_midtown_browser_live_session,
    RetailerBrowserConfigurationError,
    RetailerBrowserEnvironmentError,
    RetailerBrowserStateError,
    get_midtown_browser_session_status,
    get_midtown_browser_live_frame,
    list_midtown_browser_orders,
    key_midtown_browser_live_session,
    retry_midtown_browser_live_session,
    start_midtown_browser_session,
    type_midtown_browser_live_session,
)

LOGGER = logging.getLogger(__name__)

retailer_browser_v1_router = APIRouter(
    prefix="/api/v1/retailer-browser", tags=["Retailer Browser API v1 (P91-02)"]
)


def attach_retailer_browser_layer(app: FastAPI) -> None:
    app.include_router(retailer_browser_v1_router)


def _status_schema(
    status,
    *,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    live_session_active: bool | None = None,
    process_id: int | None = None,
    registry_contains_account: bool | None = None,
    registry_session_count: int | None = None,
) -> MidtownBrowserSessionStatusRead:
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
        viewport_width=viewport_width if viewport_width is not None else getattr(status, "viewport_width", None),
        viewport_height=viewport_height if viewport_height is not None else getattr(status, "viewport_height", None),
        live_session_active=
            live_session_active if live_session_active is not None else getattr(status, "live_session_active", None),
        process_id=process_id if process_id is not None else getattr(status, "process_id", None),
        registry_contains_account=
            registry_contains_account
            if registry_contains_account is not None
            else getattr(status, "registry_contains_account", None),
        registry_session_count=
            registry_session_count
            if registry_session_count is not None
            else getattr(status, "registry_session_count", None),
    )


@retailer_browser_v1_router.post("/midtown/session/start", response_model=MidtownBrowserSessionResponse)
def start_midtown_session(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    LOGGER.info(
        "midtown_browser_session_start_endpoint user_id=%s",
        current_user.id,
    )
    try:
        status_model = start_midtown_browser_session(session, owner_user_id=int(current_user.id))
    except RetailerBrowserConfigurationError as exc:
        LOGGER.warning(
            "midtown_browser_session_start_config_error user_id=%s detail=%s",
            current_user.id,
            exc,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        LOGGER.exception("midtown_browser_session_start_state_error user_id=%s", current_user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        LOGGER.exception("midtown_browser_session_start_environment_error user_id=%s", current_user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


@retailer_browser_v1_router.get("/midtown/session/status", response_model=MidtownBrowserSessionResponse)
def get_midtown_session_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    try:
        status_model = get_midtown_browser_session_status(session, owner_user_id=int(current_user.id))
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


@retailer_browser_v1_router.post("/midtown/go-to-orders", response_model=MidtownBrowserOrdersResponse)
def go_to_midtown_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserOrdersResponse:
    assert current_user.id is not None
    try:
        orders_model = list_midtown_browser_orders(session, owner_user_id=int(current_user.id))
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
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
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserOrdersResponse(
        session=_status_schema(orders_model.status),
        orders=[MidtownBrowserOrderRead.model_validate(order) for order in orders_model.orders],
    )


@retailer_browser_v1_router.get("/midtown/session/frame", response_model=MidtownBrowserFrameResponse)
def get_midtown_session_frame(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserFrameResponse:
    assert current_user.id is not None
    try:
        frame_payload = get_midtown_browser_live_frame(session, owner_user_id=int(current_user.id))
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserFrameResponse(
        session=_status_schema(
            frame_payload["session"],
            viewport_width=frame_payload.get("viewport_width"),
            viewport_height=frame_payload.get("viewport_height"),
            live_session_active=frame_payload.get("live_session_active"),
            process_id=frame_payload.get("process_id"),
            registry_contains_account=frame_payload.get("registry_contains_account"),
            registry_session_count=frame_payload.get("registry_session_count"),
        ),
        image_data_url=frame_payload["image_data_url"],
        image_width=frame_payload["image_width"],
        image_height=frame_payload["image_height"],
        captured_at=frame_payload["captured_at"],
        endpoint_status=frame_payload.get("endpoint_status"),
        image_bytes_size=frame_payload.get("image_bytes_size"),
        page_title=frame_payload.get("page_title"),
        page_url=frame_payload.get("page_url"),
        browser_exists=frame_payload.get("browser_exists"),
        context_exists=frame_payload.get("context_exists"),
        page_exists=frame_payload.get("page_exists"),
        process_id=frame_payload.get("process_id"),
        registry_contains_account=frame_payload.get("registry_contains_account"),
        registry_session_count=frame_payload.get("registry_session_count"),
    )


@retailer_browser_v1_router.post("/midtown/session/click", response_model=MidtownBrowserSessionResponse)
def click_midtown_session(
    payload: MidtownBrowserClickRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    try:
        status_model = click_midtown_browser_live_session(
            session,
            owner_user_id=int(current_user.id),
            x=payload.x,
            y=payload.y,
            button=payload.button,
            click_count=payload.click_count,
        )
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


@retailer_browser_v1_router.post("/midtown/session/type", response_model=MidtownBrowserSessionResponse)
def type_midtown_session(
    payload: MidtownBrowserTypeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    try:
        status_model = type_midtown_browser_live_session(
            session,
            owner_user_id=int(current_user.id),
            text=payload.text,
        )
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


@retailer_browser_v1_router.post("/midtown/session/key", response_model=MidtownBrowserSessionResponse)
def key_midtown_session(
    payload: MidtownBrowserKeyRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    try:
        status_model = key_midtown_browser_live_session(
            session,
            owner_user_id=int(current_user.id),
            key=payload.key,
        )
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


@retailer_browser_v1_router.post("/midtown/session/retry", response_model=MidtownBrowserSessionResponse)
def retry_midtown_session(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownBrowserSessionResponse:
    assert current_user.id is not None
    try:
        status_model = retry_midtown_browser_live_session(session, owner_user_id=int(current_user.id))
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserSessionResponse(session=_status_schema(status_model))


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
    except RetailerBrowserConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RetailerBrowserStateError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RetailerBrowserEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MidtownBrowserCaptureResponse(
        session=_status_schema(status_model),
        order_id=snapshot_id,
        retailer_order_number=retailer_order_number,
    )
