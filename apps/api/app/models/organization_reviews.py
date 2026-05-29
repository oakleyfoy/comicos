from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationReview(SQLModel, table=True):
    __tablename__ = "organization_reviews"
    __table_args__ = (
        SAIndex(
            "ix_org_review_org_status_requested",
            "organization_id",
            "review_status",
            "requested_at",
            "id",
        ),
        SAIndex(
            "ix_org_review_org_item_status",
            "organization_id",
            "inventory_item_id",
            "review_status",
            "id",
        ),
        SAIndex(
            "ix_org_review_org_assignee_status",
            "organization_id",
            "assigned_user_id",
            "review_status",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    review_type: str = Field(max_length=48, nullable=False, index=True)
    review_status: str = Field(max_length=24, nullable=False, index=True)
    assigned_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    created_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    requested_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OrganizationReviewDecision(SQLModel, table=True):
    __tablename__ = "organization_review_decisions"
    __table_args__ = (
        SAIndex(
            "ix_org_review_decision_review_created",
            "organization_review_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_review_id: int = Field(foreign_key="organization_reviews.id", nullable=False, index=True)
    actor_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    decision_type: str = Field(max_length=24, nullable=False, index=True)
    decision_notes: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationApprovalQueue(SQLModel, table=True):
    __tablename__ = "organization_approval_queues"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_id", name="uq_org_approval_queue_org_review"),
        SAIndex(
            "ix_org_approval_queue_org_name_pos",
            "organization_id",
            "queue_name",
            "queue_position",
            "id",
        ),
        SAIndex(
            "ix_org_approval_queue_org_status",
            "organization_id",
            "queue_status",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    queue_name: str = Field(max_length=48, nullable=False, index=True)
    review_id: int = Field(foreign_key="organization_reviews.id", nullable=False, index=True)
    queue_position: int = Field(nullable=False, index=True)
    queue_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationReviewEvent(SQLModel, table=True):
    """Append-only review workflow lineage (P42-05)."""

    __tablename__ = "organization_review_events"
    __table_args__ = (
        SAIndex("ix_org_review_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_org_review_event_review_created", "organization_review_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    organization_review_id: int | None = Field(default=None, foreign_key="organization_reviews.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=64, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
