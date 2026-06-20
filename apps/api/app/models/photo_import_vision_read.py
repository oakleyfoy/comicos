"""P100-24 GPT vision read sandbox — stores model output only (no catalog)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PhotoImportVisionRead(SQLModel, table=True):
    __tablename__ = "photo_import_vision_read"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="photo_import_session.id", index=True, nullable=False)
    image_id: int = Field(foreign_key="photo_import_image.id", index=True, nullable=False)

    publisher: str | None = Field(default=None, max_length=256, nullable=True)
    series: str | None = Field(default=None, max_length=512, nullable=True)
    issue_number: str | None = Field(default=None, max_length=64, nullable=True)
    issue_title: str | None = Field(default=None, max_length=512, nullable=True)
    variant_description: str | None = Field(default=None, max_length=512, nullable=True)

    year: str | None = Field(default=None, max_length=16, nullable=True)
    cover_date: str | None = Field(default=None, max_length=32, nullable=True)
    barcode: str | None = Field(default=None, max_length=64, nullable=True)

    confidence: float | None = Field(default=None, nullable=True)
    reasoning: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    possible_alternates: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    raw_response: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    raw_response_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    is_correct: bool | None = Field(default=None, nullable=True)
    feedback_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(default_factory=utc_now, nullable=False)
