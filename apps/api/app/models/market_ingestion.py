from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, JSON, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketAcquisitionIngestionBatch(SQLModel, table=True):
    __tablename__ = "market_acquisition_ingestion_batch"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "batch_checksum",
            name="uq_market_acquisition_ingestion_batch_owner_checksum",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    batch_source_type: str = Field(max_length=40, nullable=False, index=True)
    batch_file_name: str | None = Field(default=None, max_length=512, nullable=True)
    batch_checksum: str = Field(max_length=64, nullable=False, index=True)
    total_records: int = Field(default=0, nullable=False)
    successful_records: int = Field(default=0, nullable=False)
    failed_records: int = Field(default=0, nullable=False)
    ingestion_status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketAcquisitionCandidate(SQLModel, table=True):
    __tablename__ = "market_acquisition_candidate"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    external_source_type: str = Field(max_length=40, nullable=False, index=True)
    external_listing_id: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    source_name: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    title: str = Field(max_length=510, nullable=False, index=True)
    publisher: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    issue_number: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    variant: str | None = Field(default=None, max_length=255, nullable=True)
    condition_raw: str | None = Field(default=None, max_length=255, nullable=True)
    asking_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    currency: str | None = Field(default=None, max_length=8, nullable=True, index=True)
    external_fmv_estimate: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    raw_payload_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    ingestion_batch_id: int = Field(
        foreign_key="market_acquisition_ingestion_batch.id",
        nullable=False,
        index=True,
    )
    normalized_flag: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False, index=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketAcquisitionRawSource(SQLModel, table=True):
    __tablename__ = "market_acquisition_raw_source"

    id: int | None = Field(default=None, primary_key=True)
    ingestion_batch_id: int = Field(
        foreign_key="market_acquisition_ingestion_batch.id",
        nullable=False,
        index=True,
    )
    raw_record_json: dict = Field(sa_column=Column(JSON, nullable=False))
    raw_hash: str = Field(max_length=64, nullable=False, index=True)
    processing_status: str = Field(max_length=24, nullable=False, index=True)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketAcquisitionIngestionEvent(SQLModel, table=True):
    __tablename__ = "market_acquisition_ingestion_event"

    id: int | None = Field(default=None, primary_key=True)
    ingestion_batch_id: int = Field(
        foreign_key="market_acquisition_ingestion_batch.id",
        nullable=False,
        index=True,
    )
    event_type: str = Field(max_length=32, nullable=False, index=True)
    metadata_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
