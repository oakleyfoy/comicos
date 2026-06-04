from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PurchaseProfileType = Literal[
    "INVESTOR",
    "COLLECTOR",
    "READER",
    "VARIANT_HUNTER",
    "LONG_TERM_HOLD",
]


class PurchaseProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    profile_type: PurchaseProfileType
    display_name: str
    description: str
    is_active: bool
    created_at: str
    updated_at: str


class PurchaseProfileUpdate(BaseModel):
    profile_type: PurchaseProfileType | None = None
    display_name: str | None = None
    description: str | None = None
    is_active: bool | None = None


RatioVariantStrategy = Literal["avoid", "conservative", "balanced", "aggressive"]


class PurchasePreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    preferred_copy_count: int
    risk_tolerance: float
    variant_interest: float
    grading_interest: float
    completionist_score: float
    speculation_score: float
    ratio_variant_strategy: RatioVariantStrategy = "conservative"
    max_ratio_variant_price: float = 25.0
    high_ratio_exception_required: bool = True
    high_ratio_threshold: int = 50
    created_at: str
    updated_at: str


class PurchasePreferenceUpdate(BaseModel):
    preferred_copy_count: int | None = Field(default=None, ge=1, le=99)
    risk_tolerance: float | None = Field(default=None, ge=0.0, le=1.0)
    variant_interest: float | None = Field(default=None, ge=0.0, le=1.0)
    grading_interest: float | None = Field(default=None, ge=0.0, le=1.0)
    completionist_score: float | None = Field(default=None, ge=0.0, le=1.0)
    speculation_score: float | None = Field(default=None, ge=0.0, le=1.0)
    ratio_variant_strategy: RatioVariantStrategy | None = None
    max_ratio_variant_price: float | None = Field(default=None, ge=0.0, le=9999.0)
    high_ratio_exception_required: bool | None = None
    high_ratio_threshold: int | None = Field(default=None, ge=10, le=500)


class PurchaseProfileEngineWeightsRead(BaseModel):
    """Normalized weights for future P53-02/03 engines (output only)."""

    quantity_weight: float
    variant_weight: float
    budget_weight: float
