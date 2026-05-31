from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

PurchaseVariantAction = Literal["BUY", "WATCH", "AVOID"]
PurchaseVariantType = Literal[
    "COVER_A",
    "OPEN_ORDER",
    "INCENTIVE",
    "RATIO",
    "STORE_EXCLUSIVE",
    "UNKNOWN",
]


class PurchaseVariantRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    release_id: int
    variant_id: int | None
    cover_label: str
    variant_type: PurchaseVariantType
    recommendation: PurchaseVariantAction
    confidence_score: float
    rationale: str
    created_at: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""
    series_name: str = ""


class PurchaseVariantRecommendationListRead(BaseModel):
    items: list[PurchaseVariantRecommendationRead]
    total_items: int
    limit: int
    offset: int


class PurchaseVariantGenerateResponse(BaseModel):
    created_count: int
