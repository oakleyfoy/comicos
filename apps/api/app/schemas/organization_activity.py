from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ACTIVITY_CATEGORIES: tuple[str, ...] = (
    "organization",
    "inventory",
    "reviews",
    "storefront",
    "security",
    "permissions",
)

ActivityCategory = Literal["organization", "inventory", "reviews", "storefront", "security", "permissions"]

LINEAGE_ACTIVITY_PREFIX = "lineage."


class OrganizationActivityEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None = None
    activity_type: str
    activity_payload_json: dict[str, object] = Field(default_factory=dict)
    visibility_scope: str
    created_at: datetime
    category: str | None = None


class OrganizationNotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    target_user_id: int
    notification_type: str
    notification_title: str
    notification_body: str
    notification_status: str
    activity_event_id: int | None = None
    created_at: datetime
    read_at: datetime | None = None
    acknowledged_at: datetime | None = None


class OrganizationActivityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationActivityEventResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationNotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationNotificationResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationNotificationUnreadCountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unread_count: int


class OrganizationNotificationReceiptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_id: int
    notification_status: str
    read_at: datetime | None = None
    acknowledged_at: datetime | None = None
