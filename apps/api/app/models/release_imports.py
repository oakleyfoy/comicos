from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_import_uuid() -> str:
    return str(uuid4())


class ReleaseImportRun(SQLModel, table=True):
    __tablename__ = "release_import_run"
    __table_args__ = (
        SAIndex("ix_release_import_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_release_import_run_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    import_uuid: str = Field(default_factory=generate_import_uuid, max_length=64, nullable=False, index=True)
    import_type: str = Field(max_length=16, nullable=False, index=True)
    file_name: str = Field(default="", max_length=260, nullable=False)
    records_processed: int = Field(default=0, nullable=False)
    records_created: int = Field(default=0, nullable=False)
    records_updated: int = Field(default=0, nullable=False)
    records_failed: int = Field(default=0, nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class ReleaseImportFile(SQLModel, table=True):
    __tablename__ = "release_import_file"
    __table_args__ = (SAIndex("ix_release_import_file_run_created", "import_run_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    import_run_id: int = Field(foreign_key="release_import_run.id", nullable=False, index=True)
    file_name: str = Field(max_length=260, nullable=False)
    file_type: str = Field(max_length=16, nullable=False, index=True)
    file_size: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ReleaseImportError(SQLModel, table=True):
    __tablename__ = "release_import_error"
    __table_args__ = (SAIndex("ix_release_import_error_run_created", "import_run_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    import_run_id: int = Field(foreign_key="release_import_run.id", nullable=False, index=True)
    record_identifier: str = Field(default="", max_length=260, nullable=False)
    error_code: str = Field(max_length=64, nullable=False, index=True)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
