"""P98 acquisition + catalog-browse API schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ----- Acquisition CRUD -----


class AcquisitionCreatePayload(BaseModel):
    acquisition_type: str = "UNKNOWN"
    purchase_date: date | None = None
    seller_name: str | None = None
    seller_username: str | None = None
    total_paid: Decimal = Decimal("0.00")
    shipping_paid: Decimal = Decimal("0.00")
    tax_paid: Decimal = Decimal("0.00")
    notes: str | None = None
    expected_book_count: int | None = None


class AcquisitionUpdatePayload(BaseModel):
    acquisition_type: str | None = None
    purchase_date: date | None = None
    seller_name: str | None = None
    seller_username: str | None = None
    total_paid: Decimal | None = None
    shipping_paid: Decimal | None = None
    tax_paid: Decimal | None = None
    notes: str | None = None
    expected_book_count: int | None = None
    allocation_mode: str | None = None
    status: str | None = None


class AcquisitionInventorySummary(BaseModel):
    allocated_total: Decimal = Decimal("0.00")
    acquisition_total: Decimal = Decimal("0.00")
    unallocated: Decimal = Decimal("0.00")
    fully_allocated: bool = True
    needs_review_count: int = 0


class AcquisitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    acquisition_type: str
    purchase_date: date | None = None
    seller_name: str | None = None
    seller_username: str | None = None
    total_paid: Decimal
    shipping_paid: Decimal
    tax_paid: Decimal
    total_cost: Decimal
    notes: str | None = None
    expected_book_count: int | None = None
    actual_book_count: int
    item_count: int
    cost_per_book: Decimal
    status: str
    allocation_mode: str
    created_at: datetime
    updated_at: datetime
    inventory_summary: AcquisitionInventorySummary


class AcquisitionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acquisition_type: str
    purchase_date: date | None = None
    seller_name: str | None = None
    seller_username: str | None = None
    total_paid: Decimal
    total_cost: Decimal
    item_count: int
    cost_per_book: Decimal
    status: str
    created_at: datetime


class AcquisitionListResponse(BaseModel):
    items: list[AcquisitionListItem]
    total: int


class AcquisitionDeleteResponse(BaseModel):
    deleted_id: int
    deleted_inventory_count: int


# ----- Items / add books -----


class AddBooksItem(BaseModel):
    catalog_issue_id: int
    quantity: int = 1


class AddBooksPayload(BaseModel):
    items: list[AddBooksItem] = Field(default_factory=list)
    force_duplicate: bool = False


class AddBooksResultItem(BaseModel):
    catalog_issue_id: int
    created_count: int
    already_added: bool
    inventory_copy_ids: list[int] = Field(default_factory=list)


class AddBooksResponse(BaseModel):
    created_count: int
    results: list[AddBooksResultItem]
    duplicate_catalog_issue_ids: list[int]
    acquisition: AcquisitionRead


class AddGenericIssuePayload(BaseModel):
    series_id: int
    issue_number: str
    quantity: int = 1


class AddPlaceholderIssuePayload(BaseModel):
    """A book not yet in the ComicOS catalog, added to an acquisition."""

    title: str
    issue_number: str = ""
    publisher: str | None = None
    quantity: int = 1
    notes: str | None = None


class BulkRangePayload(BaseModel):
    series_id: int
    start_issue: int
    end_issue: int
    # How to resolve issue numbers that have multiple covers/variants.
    variant_resolution: str = "review"  # cover_a | review | generic


class BulkRangeNeedsVariant(BaseModel):
    issue_number: str
    cover_count: int


class BulkRangeResponse(BaseModel):
    added_count: int
    needs_variant: list[BulkRangeNeedsVariant]
    acquisition: AcquisitionRead


class AcquisitionItemRead(BaseModel):
    inventory_copy_id: int
    acquisition_id: int
    catalog_issue_id: int | None = None
    series: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    cover_image_url: str | None = None
    variant_label: str | None = None
    variant_status: str
    cost_basis: Decimal
    copy_number: int
    is_placeholder: bool = False
    catalog_status: str | None = None
    placeholder_issue_id: int | None = None


class AcquisitionItemsResponse(BaseModel):
    items: list[AcquisitionItemRead]
    total: int


# ----- Cost allocation -----


class AllocatePayload(BaseModel):
    mode: str = "EVEN"  # EVEN | MANUAL
    manual: dict[int, Decimal] | None = None  # inventory_copy_id -> cost_basis


class AllocateItem(BaseModel):
    inventory_copy_id: int
    cost_basis: Decimal


class AllocateResponse(BaseModel):
    mode: str
    allocated_total: Decimal
    acquisition_total: Decimal
    fully_allocated: bool
    items: list[AllocateItem]
    acquisition: AcquisitionRead


# ----- Analytics (P98-16) -----


class AcquisitionSourceAnalyticsRow(BaseModel):
    acquisition_type: str
    acquisition_count: int
    total_spend: Decimal
    book_count: int
    avg_cost_per_book: Decimal


class AcquisitionSourceAnalyticsResponse(BaseModel):
    rows: list[AcquisitionSourceAnalyticsRow]
    total_spend: Decimal
    total_books: int


# ----- Catalog browse (P98-06/07/08/09) -----


class PublisherCard(BaseModel):
    id: int
    name: str
    series_count: int = 0
    owned: bool = False
    recently_used: bool = False


class PublisherListResponse(BaseModel):
    publishers: list[PublisherCard]


class SeriesCard(BaseModel):
    id: int
    name: str
    start_year: int | None = None
    issue_count: int = 0
    publisher_id: int | None = None
    publisher_name: str | None = None
    sample_cover_url: str | None = None
    owned: bool = False
    recently_used: bool = False


class SeriesListResponse(BaseModel):
    popular: list[SeriesCard]
    recently_used: list[SeriesCard]
    user_owned: list[SeriesCard]
    alphabetical: list[SeriesCard]


class IssueGridTile(BaseModel):
    issue_number: str
    normalized_issue_number: str
    catalog_issue_id: int | None = None
    cover_image_url: str | None = None
    cover_count: int = 1
    has_variants: bool = False
    owned: bool = False
    added: bool = False


class IssueGridResponse(BaseModel):
    series_id: int
    series_name: str
    publisher_name: str | None = None
    tiles: list[IssueGridTile]


class VariantOption(BaseModel):
    catalog_issue_id: int
    series: str
    issue_number: str
    title: str | None = None
    variant_label: str | None = None
    cover_date: date | None = None
    publisher: str | None = None
    cover_image_url: str | None = None
    variant_type: str | None = None
    sort_rank: int = 0
    owned: bool = False
    added: bool = False


class VariantPickerResult(BaseModel):
    series_id: int
    issue_number: str
    options: list[VariantOption]
