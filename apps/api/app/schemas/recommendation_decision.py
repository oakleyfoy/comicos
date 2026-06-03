from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
}


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
    decision_headline: str = Field(
        description="Primary UI line, e.g. BUY 2 COPIES or WATCH",
    )
