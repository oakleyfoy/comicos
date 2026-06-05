"""P66 Variant & Market Intelligence models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P66_SOURCE_VERSION = "P66"

TIER_S = "S"
TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
VARIANT_TIERS = (TIER_S, TIER_A, TIER_B, TIER_C)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VariantIntelligenceSnapshot(SQLModel, table=True):
    __tablename__ = "variant_intelligence_snapshot"
    __table_args__ = (SAIndex("ix_variant_intel_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P66_SOURCE_VERSION, max_length=16, nullable=False)


class VariantIntelligenceItem(SQLModel, table=True):
    __tablename__ = "variant_intelligence_item"
    __table_args__ = (SAIndex("ix_variant_intel_item_snap_score", "snapshot_id", "variant_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="variant_intelligence_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True, index=True)
    external_catalog_variant_id: int | None = Field(default=None, foreign_key="external_catalog_variant.id", nullable=True, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    cover_label: str = Field(default="", max_length=64, nullable=False)
    variant_name: str = Field(default="", max_length=200, nullable=False)
    variant_score: float = Field(default=0.0, nullable=False, index=True)
    variant_tier: str = Field(default=TIER_C, max_length=2, nullable=False, index=True)
    variant_reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    provenance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class QuantityRecommendationSnapshot(SQLModel, table=True):
    __tablename__ = "quantity_recommendation_snapshot"
    __table_args__ = (SAIndex("ix_quantity_rec_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P66_SOURCE_VERSION, max_length=16, nullable=False)


class QuantityRecommendationItem(SQLModel, table=True):
    __tablename__ = "quantity_recommendation_item"
    __table_args__ = (SAIndex("ix_quantity_rec_item_snap", "snapshot_id", "buy_queue_item_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="quantity_recommendation_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    buy_queue_item_id: int | None = Field(default=None, nullable=True, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    collection_quantity: int = Field(default=0, nullable=False)
    spec_quantity: int = Field(default=0, nullable=False)
    flip_quantity: int = Field(default=0, nullable=False)
    total_quantity: int = Field(default=0, nullable=False)
    confidence: str = Field(default="MEDIUM", max_length=16, nullable=False)
    reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class MarketPriceSnapshot(SQLModel, table=True):
    __tablename__ = "market_price_snapshot"
    __table_args__ = (SAIndex("ix_market_price_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    provider: str = Field(default="STUB", max_length=32, nullable=False)
    total_observations: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P66_SOURCE_VERSION, max_length=16, nullable=False)


class MarketPriceObservation(SQLModel, table=True):
    __tablename__ = "market_price_observation"
    __table_args__ = (SAIndex("ix_market_price_obs_snap", "snapshot_id", "external_catalog_variant_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="market_price_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True, index=True)
    external_catalog_variant_id: int | None = Field(default=None, foreign_key="external_catalog_variant.id", nullable=True, index=True)
    fmv: float = Field(default=0.0, nullable=False)
    price_trend: str = Field(default="STABLE", max_length=16, nullable=False)
    liquidity: str = Field(default="MEDIUM", max_length=16, nullable=False)
    market_confidence: float = Field(default=0.5, nullable=False)
    source_key: str = Field(default="stub", max_length=32, nullable=False)
    provenance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class VariantDecisionSnapshot(SQLModel, table=True):
    __tablename__ = "variant_decision_snapshot"
    __table_args__ = (SAIndex("ix_variant_decision_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_issues: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P66_SOURCE_VERSION, max_length=16, nullable=False)


class VariantDecisionItem(SQLModel, table=True):
    __tablename__ = "variant_decision_item"
    __table_args__ = (SAIndex("ix_variant_decision_item_snap", "snapshot_id", "external_catalog_issue_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="variant_decision_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True, index=True)
    buy_queue_item_id: int | None = Field(default=None, nullable=True, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    issue_number: str = Field(default="", max_length=32, nullable=False)
    recommendation_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    cover_ranking_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    buy_plan_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    skip_covers_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    quantity_plan_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
