"""P38-06 acquisition-priority API shapes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


AcquisitionCategory = Literal[
    "DIVERSIFICATION",
    "LIQUIDITY_IMPROVEMENT",
    "GRADING_OPPORTUNITY",
    "KEY_ISSUE",
    "PORTFOLIO_GAP",
    "LOW_EXPOSURE_CATEGORY",
    "CONVENTION_STOCK",
    "SALES_VELOCITY",
]
AcquisitionPriorityLevel = Literal["LOW", "MEDIUM", "HIGH", "ELITE"]
AcquisitionRecommendationStrength = Literal["WEAK", "MODERATE", "STRONG", "ELITE"]
AcquisitionConfidenceLevel = Literal["LOW", "MEDIUM", "HIGH"]
AcquisitionRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
AcquisitionEvidenceType = Literal[
    "PORTFOLIO_EXPOSURE",
    "CONCENTRATION_RISK",
    "DUPLICATE_INTELLIGENCE",
    "PORTFOLIO_LIQUIDITY",
    "GRADING_RECOMMENDATION",
    "SALES_LEDGER",
    "MARKET_SALE",
    "LISTING_INTELLIGENCE",
]
AcquisitionScenarioName = Literal["pessimistic", "baseline", "optimistic"]


class AcquisitionPriorityGeneratePayload(BaseModel):
    model_config = {"extra": "forbid"}

    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class AcquisitionPrioritySnapshotRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    owner_user_id: int
    canonical_comic_issue_id: int | None
    acquisition_category: str
    acquisition_priority: str
    portfolio_impact_score: Decimal | None
    diversification_impact: Decimal | None
    liquidity_impact: Decimal | None
    grading_upside_score: Decimal | None
    duplication_risk: Decimal | None
    concentration_reduction_score: Decimal | None
    estimated_capital_efficiency: Decimal | None
    recommendation_strength: str
    confidence_level: str
    risk_level: str
    rationale_summary: str
    warning_flags_json: list[object]
    checksum: str
    replay_key: str | None
    snapshot_date: date
    created_at: datetime


class AcquisitionPriorityEvidenceRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    acquisition_priority_snapshot_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class AcquisitionPriorityScenarioRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    acquisition_priority_snapshot_id: int
    scenario_name: str
    projected_liquidity_impact: Decimal | None
    projected_diversification_impact: Decimal | None
    projected_portfolio_efficiency: Decimal | None
    created_at: datetime


class AcquisitionPriorityHistoryRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    owner_user_id: int
    canonical_comic_issue_id: int | None
    acquisition_category: str
    acquisition_priority: str
    recommendation_strength: str
    confidence_level: str
    risk_level: str
    checksum: str
    snapshot_date: date
    created_at: datetime


class AcquisitionPriorityDetailRead(BaseModel):
    model_config = {"extra": "forbid"}

    snapshot: AcquisitionPrioritySnapshotRead
    evidence: list[AcquisitionPriorityEvidenceRead]
    scenarios: list[AcquisitionPriorityScenarioRead]
    history: list[AcquisitionPriorityHistoryRead]


class AcquisitionPriorityListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[AcquisitionPrioritySnapshotRead]
    total: int


class AcquisitionPriorityGenerateResponse(BaseModel):
    model_config = {"extra": "forbid"}

    replayed: bool
    items: list[AcquisitionPrioritySnapshotRead]
    total: int
    history_appended_count: int


class AcquisitionPriorityEvidenceListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[AcquisitionPriorityEvidenceRead]
    total: int


class AcquisitionPriorityHistoryListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[AcquisitionPriorityHistoryRead]
    total: int


class InventoryAcquisitionPriorityTeaser(BaseModel):
    model_config = {"extra": "forbid"}

    acquisition_category: str
    acquisition_priority: str
    recommendation_strength: str
    rationale_summary: str
    diversification_impact: str | None = None
    liquidity_impact: str | None = None
    duplication_risk: str | None = None
