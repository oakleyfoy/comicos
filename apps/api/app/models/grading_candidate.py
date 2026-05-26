"""P37-01 deterministic grading candidate registry (operational ledger; no grading AI)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Numeric, Text, UniqueConstraint
from sqlalchemy import Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GradingCandidate(SQLModel, table=True):
    __tablename__ = "grading_candidate"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_candidate_owner_replay"),
        SAIndex(
            "ix_grading_candidate_owner_inventory_status",
            "owner_user_id",
            "inventory_item_id",
            "status",
            "id",
        ),
        SAIndex("ix_grading_candidate_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_grading_candidate_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    canonical_comic_issue_id: int | None = Field(
        default=None,
        foreign_key="comic_issue.id",
        nullable=True,
        index=True,
    )

    status: str = Field(max_length=24, nullable=False, index=True)
    target_grader: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True)

    estimated_raw_value: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 2), nullable=True),
    )
    estimated_graded_value: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 2), nullable=True),
    )
    estimated_spread: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 2), nullable=True),
    )
    estimated_grading_cost: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 2), nullable=True),
    )
    estimated_roi: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(18, 8), nullable=True),
    )

    candidate_priority: str = Field(max_length=16, nullable=False, index=True)
    rationale: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    submitted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    graded_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    archived_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class GradingCandidateEvidence(SQLModel, table=True):
    __tablename__ = "grading_candidate_evidence"
    __table_args__ = (
        SAIndex(
            "ix_grading_candidate_evidence_candidate_created",
            "grading_candidate_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_candidate_id: int = Field(
        foreign_key="grading_candidate.id", nullable=False, index=True
    )
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    lineage_domain: str = Field(max_length=96, nullable=False)
    lineage_key: str = Field(max_length=256, nullable=False)
    reference_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class GradingCandidateLifecycleEvent(SQLModel, table=True):
    __tablename__ = "grading_candidate_lifecycle_event"
    __table_args__ = (
        SAIndex(
            "ix_grading_candidate_lc_event_candidate_created",
            "grading_candidate_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_candidate_id: int = Field(
        foreign_key="grading_candidate.id", nullable=False, index=True
    )
    event_type: str = Field(max_length=48, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True)
    payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class GradingCandidateSnapshot(SQLModel, table=True):
    __tablename__ = "grading_candidate_snapshot"
    __table_args__ = (
        SAIndex(
            "ix_grading_candidate_snapshot_candidate_created",
            "grading_candidate_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_candidate_id: int = Field(
        foreign_key="grading_candidate.id", nullable=False, index=True
    )

    assumptions_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_count: int = Field(default=0, nullable=False, ge=0)
    checksum: str = Field(max_length=64, nullable=False)

    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
