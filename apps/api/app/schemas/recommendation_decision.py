from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.printing_intelligence import PrintingBadgeRead

PurchaseAction = Literal["BUY", "BUY_AGGRESSIVE", "WATCH", "PASS"]
DecisionRisk = Literal["LOW", "MEDIUM", "HIGH"]
DecisionStrategy = Literal[
    "FLIP",
    "HOLD",
    "SELL_ONE_KEEP_ONE",
    "LONG_TERM_HOLD",
    "GRADE_CANDIDATE",
]

REASON_CODE_LABELS: dict[str, str] = {
    "FIRST_APPEARANCE": "First appearance",
    "KEY_ISSUE": "Key issue",
    "MEDIA_CATALYST": "Media catalyst",
    "CREATOR_HEAT": "Creator heat",
    "FRANCHISE_STRENGTH": "Franchise strength",
    "COLLECTOR_CONTINUITY": "Collector continuity",
    "SCARCITY": "Scarcity",
    "RATIO_OPPORTUNITY": "Ratio opportunity",
    "FOC_URGENCY": "FOC urgency",
    "MARKET_DEMAND": "Market demand",
    "SPEC_HEAT": "Spec/market heat",
    "MULTI_SOURCE": "Multi-system signal",
    "MILESTONE_ISSUE": "Milestone issue",
    "CREATOR_SIGNIFICANCE": "Notable creator",
    "HOMAGE_TRIBUTE": "Homage or tribute cover",
    "COLLECTOR_AUDIENCE": "Active collector audience",
    "HISTORICAL_FRANCHISE": "Historical franchise relevance",
    "HIGH_CONFIDENCE": "High recommendation confidence",
    "MARKET_HEAT": "Strong market/spec signal",
    "USER_PROFILE_MATCH": "Matches user strategy",
    "PULL_LIST_RELEVANCE": "Pull list relevance",
    "NOT_IN_INVENTORY": "Not currently owned",
    "FOC_WINDOW": "FOC timing window",
    "BASE_HOLD_COPY": "Base hold copy",
    "PRIMARY_COVER_LIQUIDITY": "Primary cover liquidity",
    "VARIANT_DIVERSIFICATION": "Variant diversification",
    "SCARCITY_PREMIUM": "Scarcity premium",
    "MONITOR_ONLY": "Monitor only",
}


class SuppressedVariantRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cover_label: str
    reason_code: str
    reason_summary: str = ""


class CoverPurchasePlanRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cover_label: str
    recommended_quantity: int = Field(ge=0, le=99)
    reason_codes: list[str] = Field(default_factory=list)
    reason_summary: str = ""


class QuantityAdjustmentRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    delta: int
    reason_code: str


class QuantityReasoningRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_quantity: int = Field(ge=0, le=99)
    adjustments: list[QuantityAdjustmentRow] = Field(default_factory=list)
    final_quantity: int = Field(ge=0, le=99)


class SignalMatrixRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_launch: bool = False
    milestone_issue: bool = False
    first_appearance: bool = False
    death_or_major_event: bool = False
    anniversary_legacy: bool = False
    creator_significance: bool = False
    homage_cover: bool = False
    franchise_strength: bool = False
    active_collector_audience: bool = False
    ratio_variant_opportunity: bool = False
    market_heat: bool = False
    user_profile_match: bool = False
    pull_list_relevance: bool = False
    not_in_inventory: bool = False
    foc_window: bool = False


class SignalAbbreviationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    description: str


class ScoreBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    points: float = 0.0
    max_points: float = 0.0
    not_available: bool = False


class RecommendationDecisionRead(BaseModel):
    """Actionable purchase decision derived from ranked recommendation signals."""

    model_config = ConfigDict(extra="forbid")

    action: PurchaseAction
    quantity: int = Field(ge=0, le=99)
    cover_recommendations: list[str] = Field(default_factory=list)
    risk: DecisionRisk
    strategy: DecisionStrategy
    reason_codes: list[str] = Field(default_factory=list)
    reason_summary: list[str] = Field(default_factory=list)
    expected_roi_range: str
    foc_date: date | None = None
    release_date: date | None = None
    original_foc_date: date | None = None
    original_release_date: date | None = None
    printing_foc_date: date | None = None
    printing_release_date: date | None = None
    printing_badge: PrintingBadgeRead | None = None
    decision_headline: str = Field(
        description="Primary UI line, e.g. BUY 5 TOTAL or WATCH",
    )
    cover_purchase_plan: list[CoverPurchasePlanRow] = Field(default_factory=list)
    quantity_reasoning: QuantityReasoningRead | None = None
    signal_matrix: SignalMatrixRead | None = None
    signal_abbreviations: list[SignalAbbreviationRead] = Field(default_factory=list)
    score_breakdown: list[ScoreBreakdownRow] = Field(default_factory=list)
    top_reasons: list[str] = Field(default_factory=list)
    strategy_allocation_hint: str | None = None
    suppressed_variants: list[SuppressedVariantRow] = Field(default_factory=list)
