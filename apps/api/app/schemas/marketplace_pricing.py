from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MarketplacePricingRulePayloadErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class MarketplacePriceRecommendationGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int = Field(gt=0)
    marketplace_listing_draft_id: int = Field(gt=0)
    recommendation_type: str = Field(default="suggested_price", min_length=1, max_length=32)
    current_listing_price: Decimal | None = Field(default=None, ge=0)
    floor_price: Decimal | None = Field(default=None, ge=0)
    ceiling_price: Decimal | None = Field(default=None, ge=0)


class MarketplacePriceRecommendationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_status: str = Field(min_length=4, max_length=24)
    review_reason: str | None = Field(default=None, max_length=1000)


class MarketplaceOfferIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int = Field(gt=0)
    marketplace_listing_draft_id: int = Field(gt=0)
    marketplace_offer_identifier: str = Field(min_length=1, max_length=255)
    offer_status: str = Field(default="received", min_length=4, max_length=24)
    offer_amount: Decimal = Field(ge=0)
    offer_currency: str = Field(default="USD", min_length=3, max_length=8)
    buyer_identifier: str | None = Field(default=None, max_length=255)
    received_at: datetime | None = None
    expires_at: datetime | None = None


class MarketplaceOfferStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offer_status: str = Field(min_length=4, max_length=24)


class MarketplacePricingRuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_key: str = Field(min_length=1, max_length=80)
    rule_name: str = Field(min_length=1, max_length=255)
    rule_status: str = Field(default="active", min_length=4, max_length=24)
    rule_payload_json: dict = Field(default_factory=dict)


class MarketplacePricingRuleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_name: str | None = Field(default=None, min_length=1, max_length=255)
    rule_status: str | None = Field(default=None, min_length=4, max_length=24)
    rule_payload_json: dict | None = None


class MarketplacePriceRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    marketplace_listing_draft_id: int
    inventory_item_id: int
    recommendation_type: str
    recommended_price: Decimal
    current_listing_price: Decimal | None = None
    floor_price: Decimal | None = None
    ceiling_price: Decimal | None = None
    recommendation_reason: str
    recommendation_status: str
    generated_at: datetime
    reviewed_at: datetime | None = None


class MarketplaceOfferResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    marketplace_listing_draft_id: int
    marketplace_offer_identifier: str
    offer_status: str
    offer_amount: Decimal
    offer_currency: str
    buyer_identifier: str | None = None
    received_at: datetime
    expires_at: datetime | None = None
    created_at: datetime


class MarketplacePricingRuleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    rule_key: str
    rule_name: str
    rule_status: str
    rule_payload_json: dict = Field(default_factory=dict)
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime


class MarketplacePricingEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int | None = None
    marketplace_listing_draft_id: int | None = None
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class MarketplacePricingPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MarketplacePricingOfferSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_offers: int
    received_offers: int
    reviewed_offers: int
    accepted_internal_offers: int
    rejected_internal_offers: int
    expired_offers: int


class MarketplacePriceRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplacePriceRecommendationResponse] = Field(default_factory=list)
    permissions: MarketplacePricingPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceOfferListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceOfferResponse] = Field(default_factory=list)
    permissions: MarketplacePricingPermissionResponse
    summary: MarketplacePricingOfferSummaryResponse
    total_items: int
    limit: int
    offset: int


class MarketplacePricingRuleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplacePricingRuleResponse] = Field(default_factory=list)
    permissions: MarketplacePricingPermissionResponse
    total_items: int
    limit: int
    offset: int
