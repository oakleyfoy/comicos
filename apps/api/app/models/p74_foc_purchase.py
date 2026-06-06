"""P74-02 FOC and purchase intelligence persistence."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P74_PURCHASE_SOURCE_VERSION = "p74-02"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P74FocRecommendationSnapshot(SQLModel, table=True):
    __tablename__ = "p74_foc_recommendation_snapshot"
    __table_args__ = (
        SAIndex("ix_p74_foc_rec_snap_owner", "owner_user_id", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    foc_this_week: int = Field(default=0, nullable=False)
    foc_next_week: int = Field(default=0, nullable=False)
    foc_within_30_days: int = Field(default=0, nullable=False)
    foc_missed: int = Field(default=0, nullable=False)
    foc_unknown: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P74_PURCHASE_SOURCE_VERSION, max_length=32, nullable=False)


class P74PurchaseRecommendation(SQLModel, table=True):
    __tablename__ = "p74_purchase_recommendation"
    __table_args__ = (
        SAIndex("ix_p74_purchase_rec_owner_issue", "owner_user_id", "release_issue_id", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_id: int = Field(foreign_key="p74_foc_recommendation_snapshot.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    publisher: str = Field(max_length=120, nullable=False)
    series_name: str = Field(max_length=200, nullable=False)
    issue_number: str = Field(max_length=24, nullable=False)
    foc_date: date | None = Field(default=None, nullable=True)
    release_date: date | None = Field(default=None, nullable=True)
    foc_bucket: str = Field(max_length=32, nullable=False, index=True)
    priority_score: int = Field(default=0, nullable=False)
    purchase_action: str = Field(max_length=16, nullable=False, index=True)
    quantity_recommended: int = Field(default=0, nullable=False)
    owned_quantity: int = Field(default=0, nullable=False)
    ordered_quantity: int = Field(default=0, nullable=False)
    watchlist_match: bool = Field(default=False, nullable=False)
    reasoning: str = Field(default="", sa_column=Column(Text, nullable=False))
    scores_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P74RecommendationChangeEvent(SQLModel, table=True):
    __tablename__ = "p74_recommendation_change_event"
    __table_args__ = (
        SAIndex("ix_p74_rec_change_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    change_kind: str = Field(max_length=16, nullable=False, index=True)
    previous_action: str = Field(max_length=16, nullable=False)
    current_action: str = Field(max_length=16, nullable=False)
    previous_quantity: int = Field(default=0, nullable=False)
    current_quantity: int = Field(default=0, nullable=False)
    reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P74FocAlert(SQLModel, table=True):
    __tablename__ = "p74_foc_alert"
    __table_args__ = (
        SAIndex("ix_p74_foc_alert_snap", "snapshot_id", "alert_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_id: int = Field(foreign_key="p74_foc_recommendation_snapshot.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    alert_type: str = Field(max_length=32, nullable=False, index=True)
    title: str = Field(max_length=256, nullable=False)
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    priority_score: int = Field(default=0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
