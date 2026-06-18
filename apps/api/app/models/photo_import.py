"""P100 phone photo import session models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SESSION_STATUS_CREATED = "created"
SESSION_STATUS_ACTIVE = "active"
SESSION_STATUS_PROCESSING = "processing"
SESSION_STATUS_REVIEW_READY = "review_ready"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_EXPIRED = "expired"
SESSION_STATUS_CANCELLED = "cancelled"

IMAGE_STATUS_UPLOADED = "uploaded"
IMAGE_STATUS_QUEUED = "queued"
IMAGE_STATUS_PROCESSING = "processing"
IMAGE_STATUS_PROCESSED = "processed"
IMAGE_STATUS_FAILED = "failed"

DETECTION_STATUS_DETECTED = "detected"
DETECTION_STATUS_RECOGNIZED = "recognized"
DETECTION_STATUS_NEEDS_REVIEW = "needs_review"
DETECTION_STATUS_CONFIRMED = "confirmed"
DETECTION_STATUS_REJECTED = "rejected"

RECOGNITION_STATUS_PENDING = "pending"
RECOGNITION_STATUS_PROCESSING = "processing"
RECOGNITION_STATUS_MATCHED = "matched"
RECOGNITION_STATUS_AMBIGUOUS = "ambiguous"
RECOGNITION_STATUS_FAILED = "failed"
RECOGNITION_STATUS_UNKNOWN = "unknown"


class PhotoImportSession(SQLModel, table=True):
    __tablename__ = "photo_import_session"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    session_token: str = Field(max_length=64, unique=True, index=True, nullable=False)
    status: str = Field(max_length=32, default=SESSION_STATUS_CREATED, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    expires_at: datetime = Field(nullable=False)
    last_seen_at: datetime | None = Field(default=None, nullable=True)
    source_device: str | None = Field(default=None, max_length=128, nullable=True)
    confirmed_count: int = Field(default=0, nullable=False)
    uploaded_photo_count: int = Field(default=0, nullable=False)
    detected_book_count: int = Field(default=0, nullable=False)
    acquisition_id: int | None = Field(default=None, foreign_key="acquisitions.id", nullable=True)


class PhotoImportImage(SQLModel, table=True):
    __tablename__ = "photo_import_image"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="photo_import_session.id", index=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    original_filename: str = Field(max_length=512, default="", nullable=False)
    storage_path: str = Field(max_length=1024, nullable=False)
    mime_type: str = Field(max_length=128, default="image/jpeg", nullable=False)
    file_size: int = Field(default=0, nullable=False)
    width: int | None = Field(default=None, nullable=True)
    height: int | None = Field(default=None, nullable=True)
    status: str = Field(max_length=32, default=IMAGE_STATUS_UPLOADED, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class PhotoImportDetectedBook(SQLModel, table=True):
    __tablename__ = "photo_import_detected_book"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="photo_import_session.id", index=True, nullable=False)
    image_id: int = Field(foreign_key="photo_import_image.id", index=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    crop_path: str | None = Field(default=None, max_length=1024, nullable=True)
    bbox_x: float = Field(default=0.0, nullable=False)
    bbox_y: float = Field(default=0.0, nullable=False)
    bbox_width: float = Field(default=1.0, nullable=False)
    bbox_height: float = Field(default=1.0, nullable=False)
    status: str = Field(max_length=32, default=DETECTION_STATUS_DETECTED, nullable=False)
    recognition_status: str = Field(max_length=32, default=RECOGNITION_STATUS_PENDING, nullable=False)
    candidate_count: int = Field(default=0, nullable=False)
    selected_catalog_issue_id: int | None = Field(default=None, nullable=True)
    selected_variant_id: int | None = Field(default=None, nullable=True)
    confidence: float = Field(default=0.0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    ai_series: str | None = Field(default=None, max_length=512, nullable=True)
    ai_issue_number: str | None = Field(default=None, max_length=64, nullable=True)
    ai_publisher: str | None = Field(default=None, max_length=256, nullable=True)
    ai_subtitle_guess: str | None = Field(default=None, max_length=512, nullable=True)
    ai_variant_hint: str | None = Field(default=None, max_length=256, nullable=True)
    ai_variant_guess: str | None = Field(default=None, max_length=256, nullable=True)
    ai_cover_year: str | None = Field(default=None, max_length=16, nullable=True)
    ai_visible_title_text: str | None = Field(default=None, max_length=512, nullable=True)
    ai_visible_issue_text: str | None = Field(default=None, max_length=128, nullable=True)
    ai_visible_publisher_text: str | None = Field(default=None, max_length=256, nullable=True)
    ai_visible_character_text: str | None = Field(default=None, max_length=512, nullable=True)
    ai_uncertainty_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ai_alternate_titles: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    ai_confidence: float | None = Field(default=None, nullable=True)
    ai_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    raw_ai_response: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class PhotoImportCandidate(SQLModel, table=True):
    __tablename__ = "photo_import_candidate"

    id: int | None = Field(default=None, primary_key=True)
    detected_book_id: int = Field(foreign_key="photo_import_detected_book.id", index=True, nullable=False)
    catalog_issue_id: int = Field(nullable=False, index=True)
    variant_id: int | None = Field(default=None, nullable=True)
    publisher: str | None = Field(default=None, max_length=256, nullable=True)
    series: str | None = Field(default=None, max_length=512, nullable=True)
    issue_number: str | None = Field(default=None, max_length=64, nullable=True)
    variant_name: str | None = Field(default=None, max_length=256, nullable=True)
    cover_url: str | None = Field(default=None, max_length=2048, nullable=True)
    thumbnail_url: str | None = Field(default=None, max_length=2048, nullable=True)
    release_date: str | None = Field(default=None, max_length=32, nullable=True)
    match_score: float = Field(default=0.0, nullable=False)
    match_reason: str | None = Field(default=None, max_length=512, nullable=True)
    matched_on: str | None = Field(default=None, max_length=64, nullable=True)
    rank: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
