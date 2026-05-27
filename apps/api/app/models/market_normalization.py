from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketAcquisitionNormalizationRun(SQLModel, table=True):
    __tablename__ = "market_acquisition_normalization_run"
    __table_args__ = (
        UniqueConstraint(
            "ingestion_batch_id",
            "run_checksum",
            name="uq_market_acquisition_norm_run_batch_checksum",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    ingestion_batch_id: int = Field(
        foreign_key="market_acquisition_ingestion_batch.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    run_status: str = Field(max_length=24, nullable=False, index=True)
    total_records: int = Field(default=0, nullable=False)
    successful_records: int = Field(default=0, nullable=False)
    partial_records: int = Field(default=0, nullable=False)
    failed_records: int = Field(default=0, nullable=False)
    run_checksum: str = Field(max_length=64, nullable=False, index=True)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketAcquisitionNormalizedCandidate(SQLModel, table=True):
    __tablename__ = "market_acquisition_normalized_candidate"
    __table_args__ = (UniqueConstraint("ingestion_candidate_id", name="uq_market_acquisition_norm_candidate_unique"),)

    id: int | None = Field(default=None, primary_key=True)
    ingestion_candidate_id: int = Field(
        foreign_key="market_acquisition_candidate.id",
        nullable=False,
        index=True,
    )
    normalization_run_id: int = Field(
        foreign_key="market_acquisition_normalization_run.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    canonical_title: str = Field(max_length=510, nullable=False, index=True)
    canonical_publisher: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    canonical_issue_number: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    canonical_variant: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    normalized_condition_band: str = Field(max_length=16, nullable=False, index=True)
    normalized_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    normalized_currency: str | None = Field(default=None, max_length=8, nullable=True, index=True)
    normalized_fmv_estimate: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    normalized_liquidity_hint: str | None = Field(default=None, max_length=64, nullable=True)
    normalized_grade_potential: str | None = Field(default=None, max_length=64, nullable=True)
    canonical_key: str = Field(max_length=64, nullable=False, index=True)
    normalization_flags_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    normalization_status: str = Field(max_length=16, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketAcquisitionNormalizationIssue(SQLModel, table=True):
    __tablename__ = "market_acquisition_normalization_issue"

    id: int | None = Field(default=None, primary_key=True)
    normalization_run_id: int = Field(
        foreign_key="market_acquisition_normalization_run.id",
        nullable=False,
        index=True,
    )
    ingestion_candidate_id: int = Field(
        foreign_key="market_acquisition_candidate.id",
        nullable=False,
        index=True,
    )
    issue_type: str = Field(max_length=32, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_detail_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketAcquisitionNormalizationEvent(SQLModel, table=True):
    __tablename__ = "market_acquisition_normalization_event"

    id: int | None = Field(default=None, primary_key=True)
    normalization_run_id: int = Field(
        foreign_key="market_acquisition_normalization_run.id",
        nullable=False,
        index=True,
    )
    event_type: str = Field(max_length=32, nullable=False, index=True)
    metadata_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

