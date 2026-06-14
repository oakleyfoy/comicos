from __future__ import annotations

from fastapi import APIRouter, Body, Depends, FastAPI, File, Form, UploadFile
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.receiving import (
    ReceivingActionResponse,
    ReceivingCompletionSummaryRead,
    ReceivingConfirmPayload,
    ReceivingCorrectionPayload,
    ReceivingPurchaseAssignmentPayload,
    ReceivingSessionCreatePayload,
    ReceivingSessionCreateResponse,
    ReceivingSessionDetailRead,
    ReceivingSessionSummaryRead,
    ReceivingSkipPayload,
    ReceivingUploadResponse,
)
from app.services.receiving.receiving_service import (
    assign_receiving_purchase,
    complete_receiving_session,
    confirm_receiving_session_item,
    correct_receiving_session_item,
    create_receiving_session,
    get_receiving_session_detail,
    get_receiving_session_summary,
    skip_receiving_session_item,
    upload_receiving_session_images,
)

receiving_v1_router = APIRouter(prefix="/api/v1", tags=["Receiving API v1 (P95-02)"])


def attach_receiving_layer(app: FastAPI) -> None:
    app.include_router(receiving_v1_router)


@receiving_v1_router.post("/receiving/session", response_model=ReceivingSessionCreateResponse)
def create_session(
    payload: ReceivingSessionCreatePayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingSessionCreateResponse:
    assert current_user.id is not None
    return create_receiving_session(session, owner_user_id=int(current_user.id), payload=payload)


@receiving_v1_router.get("/receiving/session/{session_id}", response_model=ReceivingSessionDetailRead)
def get_session_detail(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingSessionDetailRead:
    assert current_user.id is not None
    return get_receiving_session_detail(session, owner_user_id=int(current_user.id), receiving_session_id=session_id)


@receiving_v1_router.post("/receiving/session/{session_id}/upload", response_model=ReceivingUploadResponse)
async def upload_session_images(
    session_id: int,
    images: list[UploadFile] = File(...),
    capture_source: str | None = Form(default=None),
    frame_fingerprint: str | None = Form(default=None),
    stable_frame_count: int = Form(default=0),
    frame_sequence_index: int | None = Form(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingUploadResponse:
    assert current_user.id is not None
    return await upload_receiving_session_images(
        session,
        owner_user_id=int(current_user.id),
        receiving_session_id=session_id,
        images=images,
        capture_source=capture_source,
        frame_fingerprint=frame_fingerprint,
        stable_frame_count=stable_frame_count,
        frame_sequence_index=frame_sequence_index,
    )


@receiving_v1_router.post("/receiving/session/{session_id}/confirm", response_model=ReceivingActionResponse)
def confirm_item(
    session_id: int,
    payload: ReceivingConfirmPayload = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingActionResponse:
    assert current_user.id is not None
    return confirm_receiving_session_item(
        session,
        owner_user_id=int(current_user.id),
        receiving_session_id=session_id,
        payload=payload,
    )


@receiving_v1_router.post("/receiving/session/{session_id}/skip", response_model=ReceivingActionResponse)
def skip_item(
    session_id: int,
    payload: ReceivingSkipPayload = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingActionResponse:
    assert current_user.id is not None
    return skip_receiving_session_item(
        session,
        owner_user_id=int(current_user.id),
        receiving_session_id=session_id,
        payload=payload,
    )


@receiving_v1_router.post(
    "/receiving/session/{session_id}/items/{item_id}/correct",
    response_model=ReceivingActionResponse,
)
def correct_item(
    session_id: int,
    item_id: int,
    payload: ReceivingCorrectionPayload = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingActionResponse:
    assert current_user.id is not None
    return correct_receiving_session_item(
        session,
        owner_user_id=int(current_user.id),
        receiving_session_id=session_id,
        item_id=item_id,
        payload=payload,
    )


@receiving_v1_router.get("/receiving/session/{session_id}/summary", response_model=ReceivingCompletionSummaryRead)
def get_session_summary(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingCompletionSummaryRead:
    assert current_user.id is not None
    return get_receiving_session_summary(
        session,
        owner_user_id=int(current_user.id),
        receiving_session_id=session_id,
    )


@receiving_v1_router.post("/receiving/session/{session_id}/assign-purchase", response_model=ReceivingSessionSummaryRead)
def assign_purchase(
    session_id: int,
    payload: ReceivingPurchaseAssignmentPayload = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingSessionSummaryRead:
    assert current_user.id is not None
    return assign_receiving_purchase(
        session,
        owner_user_id=int(current_user.id),
        receiving_session_id=session_id,
        payload=payload,
    )


@receiving_v1_router.post("/receiving/session/{session_id}/complete", response_model=ReceivingCompletionSummaryRead)
def complete_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceivingCompletionSummaryRead:
    assert current_user.id is not None
    return complete_receiving_session(
        session,
        owner_user_id=int(current_user.id),
        receiving_session_id=session_id,
    )

