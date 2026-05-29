from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ORG_INVENTORY_QUEUE_NAMES: tuple[str, ...] = (
    "intake",
    "grading_review",
    "scan_review",
    "marketplace_ready",
    "archived",
)

OrganizationInventoryQueueName = Literal[
    "intake",
    "grading_review",
    "scan_review",
    "marketplace_ready",
    "archived",
]

WORKFLOW_EVENT_TYPES: tuple[str, ...] = (
    "inventory_assigned",
    "inventory_unassigned",
    "assignment_completed",
    "queue_moved",
    "queue_created",
    "queue_removed",
    "unauthorized_inventory_access_attempt",
)


class OrganizationInventoryAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    inventory_item_id: int
    assigned_user_id: int
    assigned_by_user_id: int
    assignment_status: str
    assignment_notes: str | None = None
    assigned_at: datetime
    completed_at: datetime | None = None


class OrganizationInventoryQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    queue_name: str
    inventory_item_id: int
    queue_position: int
    queue_status: str
    created_at: datetime


class OrganizationInventoryWorkflowEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    inventory_item_id: int | None = None
    actor_user_id: int | None = None
    workflow_event_type: str
    workflow_payload_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class OrganizationInventoryAssignmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationInventoryAssignmentResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationInventoryQueueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationInventoryQueueResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationInventoryWorkflowEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationInventoryWorkflowEventResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationInventoryAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int
    assigned_user_id: int
    assignment_notes: str | None = None


class OrganizationInventoryUnassignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int
    assignment_notes: str | None = None


class OrganizationInventoryCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int
    assignment_notes: str | None = None


class OrganizationInventoryQueueMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int
    queue_name: OrganizationInventoryQueueName
    queue_position: int | None = Field(default=None, ge=1)


class OrganizationSharedInventoryAssignmentMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: int | None = None
    assigned_user_id: int | None = None
    assignment_status: str | None = None
    queue_name: str | None = None
    queue_position: int | None = None
