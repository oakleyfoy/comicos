"""P36-02 deterministic marketplace listing export (files only; no posting)."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Text, UniqueConstraint
from sqlalchemy import Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ListingExportTemplate(SQLModel, table=True):
    __tablename__ = "listing_export_template"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "channel",
            "name",
            name="uq_listing_export_tpl_owner_channel_name",
        ),
        SAIndex("ix_listing_export_tpl_owner_active", "owner_user_id", "is_active"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)

    channel: str = Field(max_length=40, nullable=False, index=True)
    name: str = Field(max_length=120, nullable=False)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    template_version: str = Field(default="1", max_length=32, nullable=False)
    column_map_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    rules_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ListingExportRun(SQLModel, table=True):
    __tablename__ = "listing_export_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_listing_export_run_owner_replay"),
        SAIndex(
            "ix_listing_export_run_owner_created_at",
            "owner_user_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)

    template_id: int = Field(foreign_key="listing_export_template.id", nullable=False, index=True)
    channel: str = Field(max_length=40, nullable=False, index=True)

    status: str = Field(max_length=24, nullable=False, index=True)
    requested_listing_count: int = Field(default=0, nullable=False)
    exported_listing_count: int = Field(default=0, nullable=False)
    skipped_listing_count: int = Field(default=0, nullable=False)
    error_count: int = Field(default=0, nullable=False)

    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    checksum: str | None = Field(default=None, max_length=64, nullable=True)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ListingExportRunItem(SQLModel, table=True):
    """Per-listing audit row for an export attempt (exported / skipped / failed)."""

    __tablename__ = "listing_export_run_item"
    __table_args__ = (
        SAIndex("ix_listing_export_item_run_row", "export_run_id", "row_number", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    export_run_id: int = Field(foreign_key="listing_export_run.id", nullable=False, index=True)
    listing_id: int | None = Field(
        default=None,
        foreign_key="listing.id",
        nullable=True,
        index=True,
    )

    status: str = Field(max_length=24, nullable=False, index=True)
    skip_reason: str | None = Field(default=None, max_length=120, nullable=True)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    row_number: int = Field(nullable=False)
    row_checksum: str | None = Field(default=None, max_length=64, nullable=True)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ListingExportFile(SQLModel, table=True):
    __tablename__ = "listing_export_file"
    __table_args__ = (
        SAIndex("ix_listing_export_file_run", "export_run_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    export_run_id: int = Field(foreign_key="listing_export_run.id", nullable=False, index=True)

    file_name: str = Field(max_length=255, nullable=False)
    file_type: str = Field(max_length=16, nullable=False)
    storage_path: str = Field(sa_column=Column(Text, nullable=False))

    checksum: str = Field(max_length=64, nullable=False)
    row_count: int = Field(default=0, nullable=False)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
