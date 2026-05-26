"""P37-04 deterministic grading submission batch ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GradingSubmissionBatch(SQLModel, table=True):
    __tablename__ = "grading_submission_batch"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_submission_batch_owner_replay"),
        SAIndex(
            "ix_grading_submission_batch_owner_status",
            "owner_user_id",
            "status",
            "target_grader",
            "id",
        ),
        SAIndex(
            "ix_grading_submission_batch_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    target_grader: str = Field(max_length=16, nullable=False, index=True)
    batch_name: str = Field(max_length=160, nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    submission_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    shipped_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    grader_received_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    grading_started_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    return_shipped_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    completed_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    estimated_turnaround_days: int | None = Field(default=None, nullable=True)
    actual_turnaround_days: int | None = Field(default=None, nullable=True)
    estimated_total_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    actual_total_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    item_count: int = Field(default=0, nullable=False, ge=0)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingSubmissionItem(SQLModel, table=True):
    __tablename__ = "grading_submission_item"
    __table_args__ = (
        SAIndex(
            "ix_grading_submission_item_batch_created",
            "grading_submission_batch_id",
            "created_at",
            "id",
        ),
        SAIndex(
            "ix_grading_submission_item_candidate",
            "grading_candidate_id",
            "status",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_submission_batch_id: int = Field(foreign_key="grading_submission_batch.id", nullable=False, index=True)
    grading_candidate_id: int = Field(foreign_key="grading_candidate.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    declared_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_grade: str | None = Field(default=None, max_length=32, nullable=True)
    final_grade: str | None = Field(default=None, max_length=32, nullable=True)
    submission_fee: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingSubmissionShipment(SQLModel, table=True):
    __tablename__ = "grading_submission_shipment"
    __table_args__ = (
        SAIndex(
            "ix_grading_submission_shipment_batch_created",
            "grading_submission_batch_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_submission_batch_id: int = Field(foreign_key="grading_submission_batch.id", nullable=False, index=True)
    shipment_direction: str = Field(max_length=16, nullable=False, index=True)
    carrier: str | None = Field(default=None, max_length=80, nullable=True)
    tracking_number: str | None = Field(default=None, max_length=120, nullable=True)
    shipped_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    delivered_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    insured_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    shipping_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingSubmissionLifecycleEvent(SQLModel, table=True):
    __tablename__ = "grading_submission_lifecycle_event"
    __table_args__ = (
        SAIndex(
            "ix_grading_submission_lifecycle_event_batch_created",
            "grading_submission_batch_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_submission_batch_id: int = Field(foreign_key="grading_submission_batch.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    prior_status: str | None = Field(default=None, max_length=24, nullable=True)
    new_status: str | None = Field(default=None, max_length=24, nullable=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingSubmissionCostSnapshot(SQLModel, table=True):
    __tablename__ = "grading_submission_cost_snapshot"
    __table_args__ = (
        SAIndex(
            "ix_grading_submission_cost_snapshot_batch_created",
            "grading_submission_batch_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_submission_batch_id: int = Field(foreign_key="grading_submission_batch.id", nullable=False, index=True)
    estimated_grading_fees: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    estimated_shipping_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    estimated_insurance_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    actual_grading_fees: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    actual_shipping_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    actual_insurance_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
