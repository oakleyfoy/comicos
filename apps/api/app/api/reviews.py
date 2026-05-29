from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.dependencies.organization_auth import require_org_permission
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.organization_reviews import (
    OrganizationReviewAssignRequest,
    OrganizationReviewCreateRequest,
    OrganizationReviewDecisionRequest,
    OrganizationReviewQueueMoveRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.review_workflow_service import (
    approve_review,
    assign_review,
    create_review,
    list_org_reviews,
    list_review_decisions,
    list_review_queues,
    move_review_queue,
    reject_review,
)

reviews_v1_router = APIRouter(prefix="/api/v1", tags=["Organization Reviews API v1 (P42-05)"])


def attach_reviews_layer(app: FastAPI) -> None:
    app.include_router(reviews_v1_router)


@reviews_v1_router.get("/organizations/{organization_id}/reviews", response_model=ScanApiV1Envelope)
def v1_list_org_reviews(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    review_status: str | None = Query(default=None),
    _: object = Depends(require_org_permission("operations:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_org_reviews(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        review_status=review_status,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@reviews_v1_router.get("/organizations/{organization_id}/reviews/queues", response_model=ScanApiV1Envelope)
def v1_list_org_review_queues(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    queue_name: str | None = Query(default=None),
    _: object = Depends(require_org_permission("operations:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_review_queues(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        queue_name=queue_name,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@reviews_v1_router.get(
    "/organizations/{organization_id}/reviews/{review_id}/decisions",
    response_model=ScanApiV1Envelope,
)
def v1_list_review_decisions(
    organization_id: int,
    review_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_org_permission("operations:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_review_decisions(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        organization_review_id=review_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@reviews_v1_router.post(
    "/organizations/{organization_id}/reviews",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_org_review(
    organization_id: int,
    payload: OrganizationReviewCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("operations:manage")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_review(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        inventory_item_id=payload.inventory_item_id,
        review_type=payload.review_type,
        assigned_user_id=payload.assigned_user_id,
        queue_name=payload.queue_name,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@reviews_v1_router.post(
    "/organizations/{organization_id}/reviews/{review_id}/assign",
    response_model=ScanApiV1Envelope,
)
def v1_assign_org_review(
    organization_id: int,
    review_id: int,
    payload: OrganizationReviewAssignRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("operations:manage")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = assign_review(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        organization_review_id=review_id,
        assigned_user_id=payload.assigned_user_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@reviews_v1_router.post(
    "/organizations/{organization_id}/reviews/{review_id}/approve",
    response_model=ScanApiV1Envelope,
)
def v1_approve_org_review(
    organization_id: int,
    review_id: int,
    payload: OrganizationReviewDecisionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("operations:manage")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = approve_review(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        organization_review_id=review_id,
        decision_notes=payload.decision_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@reviews_v1_router.post(
    "/organizations/{organization_id}/reviews/{review_id}/reject",
    response_model=ScanApiV1Envelope,
)
def v1_reject_org_review(
    organization_id: int,
    review_id: int,
    payload: OrganizationReviewDecisionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("operations:manage")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = reject_review(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        organization_review_id=review_id,
        decision_notes=payload.decision_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@reviews_v1_router.post(
    "/organizations/{organization_id}/reviews/queues/move",
    response_model=ScanApiV1Envelope,
)
def v1_move_org_review_queue(
    organization_id: int,
    payload: OrganizationReviewQueueMoveRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("operations:manage")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = move_review_queue(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        review_id=payload.review_id,
        queue_name=payload.queue_name,
        queue_position=payload.queue_position,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
