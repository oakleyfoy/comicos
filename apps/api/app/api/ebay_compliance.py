from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, Request, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.ebay_account_deletion import (
    EbayAccountDeletionAckResponse,
    EbayAccountDeletionChallengeResponse,
)
from app.services.ebay_account_deletion_compliance import (
    handle_account_deletion_notification,
    handle_verification_challenge,
)

ebay_compliance_v1_router = APIRouter(prefix="/api/v1", tags=["eBay Compliance API v1"])


def attach_ebay_compliance_layer(app: FastAPI) -> None:
    app.include_router(ebay_compliance_v1_router)


@ebay_compliance_v1_router.get(
    "/ebay/account-deletion",
    response_model=EbayAccountDeletionChallengeResponse,
    response_model_by_alias=True,
)
def v1_ebay_account_deletion_challenge(
    challenge_code: str = Query(..., description="eBay endpoint verification challenge code."),
) -> EbayAccountDeletionChallengeResponse:
    return handle_verification_challenge(challenge_code=challenge_code)


@ebay_compliance_v1_router.post(
    "/ebay/account-deletion",
    response_model=EbayAccountDeletionAckResponse,
    status_code=status.HTTP_200_OK,
)
async def v1_ebay_account_deletion_notification(
    request: Request,
    session: Session = Depends(get_session),
) -> EbayAccountDeletionAckResponse:
    raw_body = await request.body()
    return handle_account_deletion_notification(session, raw_body=raw_body)
