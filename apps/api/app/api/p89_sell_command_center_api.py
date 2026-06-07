"""P89-05 Sell Command Center API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p89_sell_command_center import SellCommandCenterRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.sell_command_center_service import build_sell_command_center

p89_sell_command_center_router = APIRouter(tags=["Sell Command Center (P89-05)"])


def attach_p89_sell_command_center_layer(app: FastAPI) -> None:
    app.include_router(p89_sell_command_center_router)


@p89_sell_command_center_router.get("/api/v1/sell-command-center", response_model=ScanApiV1Envelope)
def v1_sell_command_center(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: SellCommandCenterRead = build_sell_command_center(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
