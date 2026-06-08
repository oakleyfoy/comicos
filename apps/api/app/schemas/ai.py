from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ParseOrderRequest(BaseModel):
    raw_text: str = Field(min_length=1)

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("raw_text is required")
        return trimmed


class MetadataIdentityComponents(BaseModel):
    publisher: str = ""
    series_title: str = ""
    issue_number: str = ""
    variant: str = ""


def _normalize_optional_creator_list(
    value: list[str] | str | None,
) -> list[str] | None:
    if value is None:
        return None

    if isinstance(value, str):
        trimmed = value.strip()
        return [trimmed] if trimmed else None

    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned or None


class AiDraftOrderItem(BaseModel):
    publisher: str | None = None
    raw_publisher: str | None = None
    canonical_publisher: str | None = None
    title: str | None = None
    raw_title: str | None = None
    canonical_title: str | None = None
    release_date: str | None = None
    raw_release_date: str | None = None
    parsed_release_date: date | None = None
    parsed_release_year: int | None = None
    release_status: Literal["released", "not_released_yet", "unknown"] | None = None
    release_lifecycle_status: (
        Literal["PREORDER", "RELEASED_NOT_RECEIVED", "RECEIVED", "OVERDUE", "UNKNOWN"] | None
    ) = None
    days_until_release: int | None = None
    days_since_release: int | None = None
    is_preorder: bool | None = None
    is_released_not_received: bool | None = None
    is_overdue: bool | None = None
    lifecycle_sort_bucket: int | None = None
    lifecycle_display_label: str | None = None
    lifecycle_display_detail: str | None = None
    catalog_match_matched: bool | None = None
    catalog_match_possible: bool | None = None
    catalog_match_source: Literal["ReleaseIssue", "ExternalCatalogIssue"] | None = None
    catalog_match_source_id: int | None = None
    catalog_match_score: int | None = None
    catalog_match_title: str | None = None
    catalog_match_publisher: str | None = None
    catalog_match_issue_number: str | None = None
    catalog_match_release_date: date | None = None
    catalog_match_diagnostics: dict[str, Any] | None = None
    catalog_release_source_text: str | None = None
    catalog_resolution_debug: dict[str, Any] | None = None
    cover_image_url: str | None = None
    cover_thumbnail_url: str | None = None
    cover_image_source: str | None = None
    cover_image_source_id: int | None = None
    has_cover_image: bool | None = None
    order_status: Literal["ordered", "preordered", "shipped", "received", "cancelled"] | None = None
    purchase_date: date | None = None
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    issue_number: str | None = None
    raw_issue_number: str | None = None
    canonical_issue_number: str | None = None
    cover_name: str | None = None
    printing: str | None = None
    ratio: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None
    writers: list[str] | None = None
    raw_writers: list[str] | None = None
    canonical_writers: list[str] | None = None
    artists: list[str] | None = None
    raw_artists: list[str] | None = None
    canonical_artists: list[str] | None = None
    cover_artists: list[str] | None = None
    raw_cover_artists: list[str] | None = None
    canonical_cover_artists: list[str] | None = None
    raw_variant_text: str | None = None
    canonical_variant_text: str | None = None
    metadata_identity_key: str | None = None
    metadata_identity_components: MetadataIdentityComponents | None = None
    metadata_review_required: bool = False
    metadata_review_notes: list[str] = Field(default_factory=list)
    metadata_autofill_source: (
        Literal[
            "metadata_catalog",
            "metadata_registry",
            "metadata_prior_issue",
            "metadata_ai",
        ]
        | None
    ) = None
    publisher_autofill_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    quantity: int | None = Field(default=None, ge=1)
    raw_item_price: Decimal | None = Field(default=None, ge=0)

    @field_validator(
        "writers",
        "raw_writers",
        "canonical_writers",
        "artists",
        "raw_artists",
        "canonical_artists",
        "cover_artists",
        "raw_cover_artists",
        "canonical_cover_artists",
        mode="before",
    )
    @classmethod
    def validate_optional_creator_lists(
        cls,
        value: list[str] | str | None,
    ) -> list[str] | None:
        return _normalize_optional_creator_list(value)


DraftSourceType = Literal["ai_draft", "manual_draft", "gmail_draft"]


class ParseOrderResponse(BaseModel):
    retailer: str | None = None
    order_date: date | None = None
    source_type: DraftSourceType = "ai_draft"
    shipping_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    items: list[AiDraftOrderItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    lifecycle_enrichment_json: dict[str, int] | None = None
