from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cover_images import CoverImageRead
from app.schemas.acquisition_priority import InventoryAcquisitionPriorityTeaser
from app.schemas.duplicate_ownership import DuplicateOwnershipCopyAttachment
from app.schemas.grading_candidate import InventoryGradingCandidateBadge
from app.schemas.grading_roi import InventoryGradingRoiBadge
from app.schemas.grading_reconciliation import InventoryGradingReconciliationBadge
from app.schemas.grading_recommendation import InventoryGradingRecommendationBadge
from app.schemas.grading_risk import InventoryGradingRiskBadge
from app.schemas.grading_submission import InventoryGradingSubmissionBadge
from app.schemas.grading_spread import InventoryGradingSpreadBadge
from app.schemas.inventory_action_center import InventoryActionCenterAttachment
from app.schemas.inventory_intelligence import InventoryCopyIntelligenceSignals
from app.schemas.inventory_fmv import InventoryFmvAttachmentRead, InventoryValuationScope
from app.schemas.scan_sessions import InventoryScanSessionOriginRead
from app.schemas.inventory_risks import InventoryRiskRead
from app.schemas.duplicate_consolidation import InventoryDuplicateIntelligenceTeaser
from app.schemas.order_arrival_intelligence import OrderArrivalClassification
from app.schemas.portfolio import InventoryPortfolioIntelligenceTeaser
from app.schemas.portfolio_liquidity import InventoryPortfolioLiquidityTeaser
from app.schemas.concentration_risk import InventoryConcentrationRiskTeaser
from app.schemas.portfolio_recommendation import InventoryPortfolioRecommendationTeaser
from app.schemas.market_scoring import InventoryMarketAcquisitionScoreTeaser
from app.schemas.market_signal import InventoryMarketAcquisitionSignalTeaser
from app.schemas.run_detection import RunDetectionCopyAttachment

ReleaseCalendarPresence = Literal["present", "missing"]
InventoryAssetState = Literal["in_hand", "ordered_not_received", "preorder_not_released_yet", "cancelled"]


class InventoryRow(BaseModel):
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None
    printing: str | None
    ratio: str | None
    variant_type: str | None
    cover_artist: str | None
    retailer: str
    order_date: date
    acquisition_cost: Decimal
    current_fmv: Decimal | None
    gain_loss: Decimal | None
    current_market_fmv: Decimal | None = None
    fmv_snapshot_id: int | None = None
    fmv_method: str | None = None
    fmv_confidence_bucket: str | None = None
    fmv_liquidity_bucket: str | None = None
    fmv_volatility_bucket: str | None = None
    fmv_stale_data: bool | None = None
    fmv_currency_code: str | None = None
    valuation_scope: InventoryValuationScope | None = None
    valuation_evidence_json: dict[str, object] = Field(default_factory=dict)
    grade_status: str
    hold_status: str
    star_rating: int | None
    condition_notes: str | None
    purchase_date: date | None = None
    release_date: date | None = None
    release_year: int | None = None
    release_status: Literal["released", "not_released_yet", "unknown"]
    order_status: Literal["ordered", "preordered", "shipped", "received", "cancelled"]
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    asset_state: InventoryAssetState
    is_in_hand: bool = False
    inventory_intelligence: InventoryCopyIntelligenceSignals | None = None
    duplicate_ownership: DuplicateOwnershipCopyAttachment | None = None
    run_detection: RunDetectionCopyAttachment | None = None
    inventory_risks: list[InventoryRiskRead] = Field(default_factory=list)
    order_arrival_classifications: list[OrderArrivalClassification] = Field(default_factory=list)
    inventory_action_center: InventoryActionCenterAttachment | None = None


class InventoryListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[InventoryRow]


class InventorySummaryResponse(BaseModel):
    total_copies: int
    in_hand_copies: int
    ordered_not_received_copies: int
    preordered_copies: int
    cancelled_copies: int
    total_cost_basis: Decimal
    total_current_fmv: Decimal
    total_unrealized_gain_loss: Decimal
    raw_count: int
    graded_count: int
    hold_count: int
    sell_count: int


class InventoryDetailResponse(BaseModel):
    inventory_copy_id: int
    copy_number: int
    metadata_identity_key: str | None = None
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None
    printing: str | None
    ratio: str | None
    variant_type: str | None
    cover_artist: str | None
    retailer: str
    order_date: date
    source_type: str | None
    acquisition_cost: Decimal
    current_fmv: Decimal | None
    current_market_fmv: Decimal | None = None
    fmv_snapshot_id: int | None = None
    fmv_method: str | None = None
    fmv_confidence_bucket: str | None = None
    fmv_liquidity_bucket: str | None = None
    fmv_volatility_bucket: str | None = None
    fmv_stale_data: bool | None = None
    fmv_currency_code: str | None = None
    valuation_scope: InventoryValuationScope | None = None
    valuation_evidence_json: dict[str, object] = Field(default_factory=dict)
    gain_loss: Decimal | None
    grade_status: str
    hold_status: str
    star_rating: int | None
    condition_notes: str | None
    order_id: int
    order_item_id: int
    variant_id: int
    purchase_date: date | None = None
    release_date: date | None = None
    release_year: int | None = None
    release_status: Literal["released", "not_released_yet", "unknown"]
    order_status: Literal["ordered", "preordered", "shipped", "received", "cancelled"]
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    asset_state: InventoryAssetState
    is_in_hand: bool = False
    created_at: datetime
    cover_images: list[CoverImageRead] = Field(default_factory=list)
    inventory_intelligence: InventoryCopyIntelligenceSignals | None = None
    duplicate_ownership: DuplicateOwnershipCopyAttachment | None = None
    run_detection: RunDetectionCopyAttachment | None = None
    inventory_risks: list[InventoryRiskRead] = Field(default_factory=list)
    order_arrival_classifications: list[OrderArrivalClassification] = Field(default_factory=list)
    inventory_action_center: InventoryActionCenterAttachment | None = None
    inventory_fmv: InventoryFmvAttachmentRead | None = None
    originating_scan_session: InventoryScanSessionOriginRead | None = None
    grading_candidate: InventoryGradingCandidateBadge | None = None
    grading_spread: InventoryGradingSpreadBadge | None = None
    grading_roi: InventoryGradingRoiBadge | None = None
    grading_submission: InventoryGradingSubmissionBadge | None = None
    grading_reconciliation: InventoryGradingReconciliationBadge | None = None
    grading_recommendation: InventoryGradingRecommendationBadge | None = None
    grading_risk: InventoryGradingRiskBadge | None = None
    portfolio_intelligence: InventoryPortfolioIntelligenceTeaser | None = None
    duplicate_intelligence: InventoryDuplicateIntelligenceTeaser | None = None
    portfolio_liquidity: InventoryPortfolioLiquidityTeaser | None = None
    acquisition_priority: InventoryAcquisitionPriorityTeaser | None = None
    concentration_risk: InventoryConcentrationRiskTeaser | None = None
    portfolio_recommendation: InventoryPortfolioRecommendationTeaser | None = None
    market_acquisition_score: InventoryMarketAcquisitionScoreTeaser | None = None
    market_acquisition_signal: InventoryMarketAcquisitionSignalTeaser | None = None


class InventoryFmvSnapshotResponse(BaseModel):
    id: int
    previous_fmv: Decimal | None
    new_fmv: Decimal
    changed_at: datetime
    source: str


class PortfolioPerformanceItem(BaseModel):
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None
    current_fmv: Decimal | None
    gain_loss: Decimal | None


class PortfolioPerformanceResponse(BaseModel):
    total_cost_basis: Decimal
    total_current_fmv: Decimal
    total_unrealized_gain_loss: Decimal
    top_gainers: list[PortfolioPerformanceItem]
    top_losers: list[PortfolioPerformanceItem]
    highest_value_books: list[PortfolioPerformanceItem]


class InventoryUpdate(BaseModel):
    current_fmv: Decimal | None = Field(default=None, ge=0)
    hold_status: Literal["hold", "sell", "sold"] | None = None
    star_rating: int | None = Field(default=None, ge=1, le=5)
    grade_status: Literal["raw", "submitted", "graded"] | None = None
    condition_notes: str | None = Field(default=None, max_length=2000)
    release_status: Literal["released", "not_released_yet", "unknown"] | None = None
    order_status: Literal["ordered", "preordered", "shipped", "received", "cancelled"] | None = None
    expected_ship_date: date | None = None
    received_at: datetime | None = None


class BulkInventoryUpdateRequest(BaseModel):
    inventory_copy_ids: list[int] = Field(min_length=1)
    updates: InventoryUpdate


class BulkInventoryUpdateResponse(BaseModel):
    updated_count: int
