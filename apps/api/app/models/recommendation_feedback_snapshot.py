"""P73-03 recommendation feedback intelligence snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel

P73_FEEDBACK_SOURCE_VERSION = "p73-03"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P73RecommendationFeedbackBundleSnapshot(SQLModel, table=True):
    """Parent row linking confidence, effectiveness, and calibration snapshots."""

    __tablename__ = "p73_recommendation_feedback_bundle_snapshot"
    __table_args__ = (
        SAIndex("ix_p73_rec_fb_bundle_owner_gen", "owner_user_id", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    overall_accuracy_pct: float = Field(default=0.0, nullable=False)
    overall_roi_pct: float = Field(default=0.0, nullable=False)
    source_version: str = Field(default=P73_FEEDBACK_SOURCE_VERSION, max_length=32, nullable=False)


class P73RecommendationConfidenceSnapshot(SQLModel, table=True):
    __tablename__ = "p73_recommendation_confidence_snapshot"
    __table_args__ = (
        SAIndex("ix_p73_rec_conf_bundle", "bundle_snapshot_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    bundle_snapshot_id: int = Field(
        foreign_key="p73_recommendation_feedback_bundle_snapshot.id",
        nullable=False,
        index=True,
    )
    buy_confidence: int = Field(default=0, nullable=False)
    grade_confidence: int = Field(default=0, nullable=False)
    sell_confidence: int = Field(default=0, nullable=False)
    watch_confidence: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P73_FEEDBACK_SOURCE_VERSION, max_length=32, nullable=False)


class P73RecommendationEffectivenessSnapshot(SQLModel, table=True):
    __tablename__ = "p73_recommendation_effectiveness_snapshot"
    __table_args__ = (
        SAIndex("ix_p73_rec_eff_bundle", "bundle_snapshot_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    bundle_snapshot_id: int = Field(
        foreign_key="p73_recommendation_feedback_bundle_snapshot.id",
        nullable=False,
        index=True,
    )
    win_rate_pct: float = Field(default=0.0, nullable=False)
    loss_rate_pct: float = Field(default=0.0, nullable=False)
    expected_roi_pct: float = Field(default=0.0, nullable=False)
    actual_roi_pct: float = Field(default=0.0, nullable=False)
    recommendation_accuracy_pct: float = Field(default=0.0, nullable=False)
    by_type_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P73_FEEDBACK_SOURCE_VERSION, max_length=32, nullable=False)


class P73RecommendationCategoryCalibrationSnapshot(SQLModel, table=True):
    __tablename__ = "p73_recommendation_category_calibration_snapshot"
    __table_args__ = (
        SAIndex("ix_p73_rec_calib_bundle_cat", "bundle_snapshot_id", "calibration_category", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    bundle_snapshot_id: int = Field(
        foreign_key="p73_recommendation_feedback_bundle_snapshot.id",
        nullable=False,
        index=True,
    )
    calibration_category: str = Field(max_length=48, nullable=False, index=True)
    recommendation_count: int = Field(default=0, nullable=False)
    success_rate_pct: float = Field(default=0.0, nullable=False)
    average_roi_pct: float = Field(default=0.0, nullable=False)
    median_roi_pct: float = Field(default=0.0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P73_FEEDBACK_SOURCE_VERSION, max_length=32, nullable=False)
