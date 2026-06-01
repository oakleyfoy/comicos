from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.industry_publisher import IndustryPublisherListRead, IndustryPublisherUpdate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.industry_publisher_scan_config import list_industry_publishers, update_industry_publisher

industry_publishers_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Industry Publishers API v1 (P59-01)"],
)


def attach_industry_publishers_layer(app: FastAPI) -> None:
    app.include_router(industry_publishers_v1_router)


@industry_publishers_v1_router.get("/industry-publishers", response_model=ScanApiV1Envelope)
def v1_list_industry_publishers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_industry_publishers(session, owner_user_id=int(current_user.id))
    body = IndustryPublisherListRead(items=items, total_items=len(items))
    return wrap_object(body, owner_user_id=int(current_user.id))


@industry_publishers_v1_router.patch("/industry-publishers/{publisher_id}", response_model=ScanApiV1Envelope)
def v1_patch_industry_publisher(
    publisher_id: int,
    payload: IndustryPublisherUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_industry_publisher(
        session,
        owner_user_id=int(current_user.id),
        publisher_id=publisher_id,
        update=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
