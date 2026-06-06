"""P80-03 collector shopping assistant API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.collection_gap import CollectionGapRead
from app.schemas.mobile_scan_platform import (
    P80BookIntelligenceRead,
    P80ScanIdentificationRead,
)
from app.schemas.p77_personalization import P77PersonalizationSnapshotRead

CollectorShoppingAction = Literal["BUY", "PASS", "HOLD", "SELL", "GRADE", "WATCH"]
PriceBuyAssessment = Literal["GREAT_BUY", "FAIR_BUY", "OVERPRICED", "UNKNOWN"]


class P80CollectorScanRequest(BaseModel):
    barcode: str | None = None
    manual_entry: str | None = None
    vendor_price: float | None = Field(default=None, ge=0, description="Optional asking price while shopping.")


class P80CollectionCompletionRead(BaseModel):
    label: str = ""
    owned_issue_count: int = 0
    known_issue_count: int = 0
    completion_percent: float | None = None
    missing_issue_numbers: list[str] = Field(default_factory=list)
    suggested_next_purchases: list[str] = Field(default_factory=list)
    scanned_issue_is_missing: bool = False
    gap_completion_opportunity: bool = False


class P80SpecOpportunityRead(BaseModel):
    detected: bool = False
    score: float | None = None
    signals: list[str] = Field(default_factory=list)
    recommendation: str | None = None


class P80CollectorActionCardRead(BaseModel):
    action: CollectorShoppingAction
    reasons: list[str] = Field(default_factory=list)
    inventory_target_exceeded: bool = False


class P80PriceAssessmentRead(BaseModel):
    asking_price: float
    authoritative_fmv: float | None = None
    spread_percent: float | None = None
    assessment: PriceBuyAssessment = "UNKNOWN"


class P80CollectorScanResultRead(BaseModel):
    identification: P80ScanIdentificationRead
    book_intelligence: P80BookIntelligenceRead | None = None
    collection_completion: P80CollectionCompletionRead | None = None
    spec_opportunity: P80SpecOpportunityRead | None = None
    action_card: P80CollectorActionCardRead
    price_assessment: P80PriceAssessmentRead | None = None
    personalization: P77PersonalizationSnapshotRead | None = None


class P80CollectorPriceEvalRequest(BaseModel):
    asking_price: float = Field(gt=0)
    barcode: str | None = None
    manual_entry: str | None = None
    inventory_id: int | None = None
    authoritative_fmv: float | None = Field(
        default=None,
        description="Optional FMV override when already known from a prior scan.",
    )


class P80CollectorPriceEvalResultRead(BaseModel):
    identification: P80ScanIdentificationRead | None = None
    price_assessment: P80PriceAssessmentRead
    action_card: P80CollectorActionCardRead | None = None
    personalization: P77PersonalizationSnapshotRead | None = None


class P80CollectorGapListResponse(BaseModel):
    items: list[CollectionGapRead]
    total_items: int
    limit: int
    offset: int


class P80CollectorOpportunityItemRead(BaseModel):
    kind: str
    title: str
    subtitle: str = ""
    score: float | None = None
    recommendation: str | None = None
    rationale: str | None = None


class P80CollectorOpportunityListResponse(BaseModel):
    items: list[P80CollectorOpportunityItemRead]
    total_items: int
    limit: int
    offset: int


class P80CollectorDashboardRead(BaseModel):
    gap_summary: dict[str, int | float] = Field(default_factory=dict)
    collection_gaps: list[CollectionGapRead] = Field(default_factory=list)
    recommended_acquisitions: list[P80CollectorOpportunityItemRead] = Field(default_factory=list)
    spec_opportunities: list[P80CollectorOpportunityItemRead] = Field(default_factory=list)
    books_to_watch: list[P80CollectorOpportunityItemRead] = Field(default_factory=list)
