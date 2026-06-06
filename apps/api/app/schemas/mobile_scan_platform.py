"""P80-01 mobile scan platform API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class P80MobileScanCreateRequest(BaseModel):
    barcode: str | None = None
    image: str | None = Field(default=None, description="Optional image reference for future OCR workflows.")
    manual_entry: str | None = None


class P80BookIdentificationRead(BaseModel):
    cover_image_url: str | None = None
    title: str
    series_name: str = ""
    issue_number: str = ""
    variant_description: str = ""
    publisher: str = ""
    release_date: str | None = None
    identification_source: str = ""
    book_identity_key: str = ""


class P80ScanIdentificationRead(BaseModel):
    confidence: str
    requires_manual_review: bool
    scan_source: str
    normalized_barcode: str = ""
    book: P80BookIdentificationRead | None = None
    storage_entity: dict | None = None


class P80OwnershipIntelligenceRead(BaseModel):
    owned: bool
    total_copies: int = 0
    graded_copies: int = 0
    raw_copies: int = 0
    inventory_copy_ids: list[int] = Field(default_factory=list)


class P80FmvIntelligenceRead(BaseModel):
    authoritative_fmv: float | None = None
    confidence_score: float | None = None
    liquidity_rating: str | None = None
    sales_velocity: float | None = None
    price_trend_30d: str | None = None


class P80RecommendationIntelligenceRead(BaseModel):
    recommendation: str | None = None
    conviction_score: float | None = None
    confidence_score: float | None = None
    rationale: str | None = None
    source_system: str | None = None


class P80GradingIntelligenceRead(BaseModel):
    grade_recommendation: str | None = None
    press_recommendation: str | None = None
    expected_grade: str | None = None
    estimated_roi_pct: float | None = None


class P80StorageLocationRead(BaseModel):
    inventory_copy_id: int
    location_path_text: str
    box_name: str | None = None
    slot_number: int | None = None


class P80StorageIntelligenceRead(BaseModel):
    locations: list[P80StorageLocationRead] = Field(default_factory=list)


class P80ActionCardRead(BaseModel):
    action: str
    reasons: list[str] = Field(default_factory=list)


class P80BookIntelligenceRead(BaseModel):
    inventory_id: int | None = None
    ownership: P80OwnershipIntelligenceRead
    fmv: P80FmvIntelligenceRead
    recommendation: P80RecommendationIntelligenceRead
    grading: P80GradingIntelligenceRead
    storage: P80StorageIntelligenceRead
    action_card: P80ActionCardRead


class P80MobileScanResultRead(BaseModel):
    scan_id: int
    created_at: datetime
    identification: P80ScanIdentificationRead
    book_intelligence: P80BookIntelligenceRead | None = None


class P80MobileScanListResponse(BaseModel):
    items: list[P80MobileScanResultRead]
    total_items: int
    limit: int = 25
    offset: int = 0
