"""P66 API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VariantIntelligenceItemRead(BaseModel):
    id: int
    cover_label: str
    variant_name: str
    variant_score: float
    variant_tier: str
    variant_reason: str
    external_catalog_issue_id: int | None = None
    factors_json: dict[str, Any] = Field(default_factory=dict)


class VariantIntelligenceSnapshotRead(BaseModel):
    snapshot_id: int | None = None
    readiness_status: str = "NOT_READY"
    generated_at: datetime | None = None
    total_items: int = 0
    items: list[VariantIntelligenceItemRead] = Field(default_factory=list)


class QuantityRecommendationItemRead(BaseModel):
    id: int
    title: str
    collection_quantity: int
    spec_quantity: int
    flip_quantity: int
    total_quantity: int
    confidence: str
    reason: str
    buy_queue_item_id: int | None = None


class QuantityRecommendationSnapshotRead(BaseModel):
    snapshot_id: int | None = None
    readiness_status: str = "NOT_READY"
    total_items: int = 0
    items: list[QuantityRecommendationItemRead] = Field(default_factory=list)


class MarketPriceObservationRead(BaseModel):
    id: int
    fmv: float
    price_trend: str
    liquidity: str
    market_confidence: float
    external_catalog_variant_id: int | None = None


class MarketPriceSnapshotRead(BaseModel):
    snapshot_id: int | None = None
    provider: str = "STUB"
    total_observations: int = 0
    observations: list[MarketPriceObservationRead] = Field(default_factory=list)


class VariantDecisionItemRead(BaseModel):
    id: int
    title: str
    issue_number: str
    recommendation_summary: str
    cover_ranking_json: list[Any] = Field(default_factory=list)
    buy_plan_json: list[Any] = Field(default_factory=list)
    skip_covers_json: list[Any] = Field(default_factory=list)
    quantity_plan_json: dict[str, Any] = Field(default_factory=dict)


class VariantDecisionSnapshotRead(BaseModel):
    snapshot_id: int | None = None
    readiness_status: str = "NOT_READY"
    total_issues: int = 0
    items: list[VariantDecisionItemRead] = Field(default_factory=list)


class P66BuildResultRead(BaseModel):
    variant_intelligence_snapshot_id: int
    market_price_snapshot_id: int
    quantity_snapshot_id: int
    variant_decision_snapshot_id: int


class P66IntegrationRead(BaseModel):
    readiness_status: str = "NOT_READY"
    decisions: list[VariantDecisionItemRead] = Field(default_factory=list)
    quantity_items: list[QuantityRecommendationItemRead] = Field(default_factory=list)


class P66CertificationRead(BaseModel):
    certified: bool
    platform_ready: bool
    checks: dict[str, Any] = Field(default_factory=dict)
    non_mutation: dict[str, Any] = Field(default_factory=dict)
    build: dict[str, Any] = Field(default_factory=dict)


class P66BuildResultEnvelope(BaseModel):
    status: str = "SUCCESS"
    snapshot_ids: P66BuildResultRead


class P66SnapshotBuildRead(BaseModel):
    snapshot_id: int
    total_items: int | None = None
    total_issues: int | None = None
    total_observations: int | None = None
