"""P37-05 deterministic grading reconciliation ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GradingReconciliationRecord(SQLModel, table=True):
    __tablename__ = "grading_reconciliation_record"
    __table_args__ = (
        SAIndex(
            "ix_grading_reconciliation_record_owner_status",
            "owner_user_id",
            "reconciliation_status",
            "grading_accuracy_status",
            "id",
        ),
        SAIndex(
            "ix_grading_reconciliation_record_owner_created",
            "owner_user_id",
            "created_at",
            "id",
        ),
        UniqueConstraint(
            "grading_submission_item_id",
            "checksum",
            name="uq_grading_reconciliation_item_checksum",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    grading_submission_item_id: int = Field(foreign_key="grading_submission_item.id", nullable=False, index=True)
    grading_candidate_id: int = Field(foreign_key="grading_candidate.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    target_grader: str = Field(max_length=16, nullable=False, index=True)
    expected_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    final_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    expected_raw_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    expected_graded_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    realized_graded_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    expected_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    realized_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    roi_delta: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    grading_accuracy_status: str = Field(max_length=24, nullable=False, index=True)
    reconciliation_status: str = Field(max_length=24, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    reconciled_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingReconciliationEvidence(SQLModel, table=True):
    __tablename__ = "grading_reconciliation_evidence"
    __table_args__ = (
        SAIndex(
            "ix_grading_reconciliation_evidence_record_created",
            "grading_reconciliation_record_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_reconciliation_record_id: int = Field(
        foreign_key="grading_reconciliation_record.id",
        nullable=False,
        index=True,
    )
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingReconciliationHistory(SQLModel, table=True):
    __tablename__ = "grading_reconciliation_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "target_grader",
            "expected_grade",
            "actual_grade",
            "snapshot_date",
            "checksum",
            name="uq_grading_reconciliation_history_signature",
        ),
        SAIndex(
            "ix_grading_reconciliation_history_owner_target_date",
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "target_grader",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    grading_candidate_id: int | None = Field(default=None, foreign_key="grading_candidate.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    target_grader: str = Field(max_length=16, nullable=False, index=True)
    expected_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    actual_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    realized_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    roi_delta: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GraderPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "grader_performance_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "grader",
            "snapshot_date",
            "checksum",
            name="uq_grader_performance_snapshot_signature",
        ),
        SAIndex(
            "ix_grader_performance_snapshot_owner_grader_date",
            "owner_user_id",
            "grader",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    grader: str = Field(max_length=16, nullable=False, index=True)
    submission_count: int = Field(default=0, nullable=False, ge=0)
    above_expectation_count: int = Field(default=0, nullable=False, ge=0)
    met_expectation_count: int = Field(default=0, nullable=False, ge=0)
    below_expectation_count: int = Field(default=0, nullable=False, ge=0)
    average_roi_delta: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    average_turnaround_days: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
