"""P37-06 schemas for deterministic grading recommendations."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GradingRecommendationAction = Literal["GRADE", "HOLD_RAW", "REVIEW_MANUALLY", "NOT_RECOMMENDED"]
GradingRecommendationStrength = Literal["WEAK", "MODERATE", "STRONG", "ELITE"]
GradingRecommendationRisk = Literal["LOW", "MEDIUM", "HIGH"]
GradingRecommendationStatus = Literal["ACTIVE", "SUPERSEDED", "ARCHIVED"]
GradingRecommendationTargetGrader = Literal["PSA", "CGC", "CBCS"]
GradingRecommendationEvidenceType = Literal[
    "ROI_ENGINE",
    "SPREAD_ENGINE",
    "LIQUIDITY",
    "RECONCILIATION",
    "GRADER_PERFORMANCE",
    "SALES_LEDGER",
    "LISTING_INTELLIGENCE",
    "MARKET_SALE",
]
GradingRecommendationScenarioName = Literal["pessimistic", "baseline", "optimistic"]


class GradingRecommendationGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_candidate_id: int | None = Field(default=None, ge=1)
    inventory_item_id: int | None = Field(default=None, ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class GradingRecommendationEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_recommendation_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class GradingRecommendationScenarioRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_recommendation_id: int
    scenario_name: str
    target_grade: str | None
    estimated_value: Decimal | None
    estimated_roi: Decimal | None
    confidence_modifier: Decimal | None
    created_at: datetime


class GradingRecommendationHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int | None
    grading_candidate_id: int | None
    inventory_item_id: int | None
    recommended_action: str
    recommended_grader: str | None
    recommendation_strength: str
    confidence_score: Decimal
    snapshot_date: date
    checksum: str
    created_at: datetime


class GradingRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    grading_candidate_id: int | None
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    recommended_action: str
    recommended_grader: str | None
    recommended_grade_target: str | None
    expected_roi: Decimal | None
    liquidity_adjusted_roi: Decimal | None
    estimated_net_profit: Decimal | None
    estimated_total_cost: Decimal | None
    confidence_score: Decimal
    overall_confidence_level: str | None = None
    recommendation_strength: str
    risk_level: str
    grading_risk_snapshot_id: int | None = None
    overall_risk_level: str | None = None
    risk_adjusted_roi: Decimal | None = None
    confidence_weight: Decimal | None = None
    recommendation_status: str
    rationale_summary: str
    warning_flags_json: list[object]
    evidence_count: int
    checksum: str
    replay_key: str | None
    snapshot_date: date
    created_at: datetime


class GradingRecommendationDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: GradingRecommendationRead
    evidence: list[GradingRecommendationEvidenceRead]
    scenarios: list[GradingRecommendationScenarioRead]
    history: list[GradingRecommendationHistoryRead]


class GradingRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRecommendationRead]
    total_items: int
    limit: int
    offset: int


class GradingRecommendationEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRecommendationEvidenceRead]
    total_items: int
    limit: int
    offset: int


class GradingRecommendationHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRecommendationHistoryRead]
    total_items: int
    limit: int
    offset: int


class GradingRecommendationDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade_recommendation_count: int
    hold_raw_count: int
    elite_opportunity_count: int
    high_risk_count: int
    average_expected_roi: Decimal | None


class InventoryGradingRecommendationBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_recommendation_id: int
    recommended_action: str
    recommended_grader: str | None
    recommended_grade_target: str | None
    confidence_score: Decimal
    overall_confidence_level: str | None = None
    risk_level: str
    grading_risk_snapshot_id: int | None = None
    overall_risk_level: str | None = None
    risk_adjusted_roi: Decimal | None = None
    recommendation_strength: str
    rationale_summary: str
