from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationInventoryAssignment(SQLModel, table=True):
    __tablename__ = "organization_inventory_assignments"
    __table_args__ = (
        SAIndex(
            "ix_org_inv_assign_org_item_status",
            "organization_id",
            "inventory_item_id",
            "assignment_status",
            "assigned_at",
            "id",
        ),
        SAIndex(
            "ix_org_inv_assign_org_user_status",
            "organization_id",
            "assigned_user_id",
            "assignment_status",
            "assigned_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    assigned_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    assigned_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    assignment_status: str = Field(max_length=24, nullable=False, index=True)
    assignment_notes: str | None = Field(default=None, nullable=True)
    assigned_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OrganizationInventoryWorkflowEvent(SQLModel, table=True):
    __tablename__ = "organization_inventory_workflow_events"
    __table_args__ = (
        SAIndex(
            "ix_org_inv_wf_event_org_created",
            "organization_id",
            "created_at",
            "id",
        ),
        SAIndex(
            "ix_org_inv_wf_event_org_item_created",
            "organization_id",
            "inventory_item_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    workflow_event_type: str = Field(max_length=64, nullable=False, index=True)
    workflow_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationInventoryQueue(SQLModel, table=True):
    __tablename__ = "organization_inventory_queues"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "inventory_item_id",
            name="uq_org_inv_queue_org_item",
        ),
        SAIndex(
            "ix_org_inv_queue_org_name_pos",
            "organization_id",
            "queue_name",
            "queue_position",
            "id",
        ),
        SAIndex(
            "ix_org_inv_queue_org_status",
            "organization_id",
            "queue_status",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    queue_name: str = Field(max_length=48, nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    queue_position: int = Field(nullable=False, index=True)
    queue_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
