from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ORG_REVIEW_QUEUE_NAMES: tuple[str, ...] = (
    "intake_review",
    "grading_review",
    "authentication_review",
    "marketplace_approval",
    "archival_review",
)

OrganizationReviewQueueName = Literal[
    "intake_review",
    "grading_review",
    "authentication_review",
    "marketplace_approval",
    "archival_review",
]

REVIEW_EVENT_TYPES: tuple[str, ...] = (
    "review_created",
    "review_assigned",
    "review_approved",
    "review_rejected",
    "review_completed",
    "queue_moved",
    "unauthorized_review_access_attempt",
)


class OrganizationReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    inventory_item_id: int
    review_type: str
    review_status: str
    assigned_user_id: int | None = None
    created_by_user_id: int
    requested_at: datetime
    completed_at: datetime | None = None
    approval_queue_name: str | None = None
    approval_queue_position: int | None = None


class OrganizationReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_review_id: int
    actor_user_id: int
    decision_type: str
    decision_notes: str | None = None
    created_at: datetime


class OrganizationApprovalQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    queue_name: str
    review_id: int
    queue_position: int
    queue_status: str
    created_at: datetime


class OrganizationReviewListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationReviewResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationReviewDecisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationReviewDecisionResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationApprovalQueueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationApprovalQueueResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationReviewCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int
    review_type: str = Field(min_length=1, max_length=48)
    assigned_user_id: int | None = None
    queue_name: OrganizationReviewQueueName | None = None


class OrganizationReviewAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_user_id: int


class OrganizationReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_notes: str | None = None


class OrganizationReviewQueueMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: int
    queue_name: OrganizationReviewQueueName
    queue_position: int | None = Field(default=None, ge=1)
