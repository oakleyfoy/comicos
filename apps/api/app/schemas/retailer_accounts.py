from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RetailerKey = Literal["midtown"]


class RetailerAccountCreate(BaseModel):
    retailer: RetailerKey = "midtown"
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=500)
    display_name: str | None = Field(default=None, max_length=200)
    sync_enabled: bool = False


class RetailerAccountUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=320)
    password: str | None = Field(default=None, min_length=1, max_length=500)
    display_name: str | None = Field(default=None, max_length=200)
    sync_enabled: bool | None = None
    status: str | None = Field(default=None, max_length=32)


class RetailerAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer: str
    display_name: str | None = None
    masked_username: str
    credential_version: int
    status: str
    sync_enabled: bool
    last_sync_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class RetailerSyncRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer_account_id: int
    retailer: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    orders_seen: int
    orders_imported: int
    items_seen: int
    items_imported: int
    items_updated: int
    errors_count: int
    summary_json: dict = Field(default_factory=dict)
    error_message: str | None = None


class RetailerOrderItemSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer_item_id: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    title: str
    publisher: str | None = None
    issue_number: str | None = None
    cover_name: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None
    quantity: int
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    item_status: str | None = None
    shipped_qty: int | None = None
    backordered_qty: int | None = None
    unavailable_qty: int | None = None
    returned_qty: int | None = None
    release_date: date | None = None
    enrichment_status: str | None = None
    enrichment_confidence: float | None = None
    catalog_match_id: int | None = None
    enrichment_notes: str | None = None
    cover_image_url: str | None = None
    source_image_url: str | None = None
    updated_at: datetime


class RetailerOrderSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer_account_id: int
    retailer: str
    retailer_order_number: str
    order_date: date | None = None
    order_status: str | None = None
    order_total: Decimal | None = None
    source_url: str | None = None
    draft_import_id: int | None = None
    review_status: str = "captured"
    item_count: int = 0
    cover_image_count: int = 0
    product_url_count: int = 0
    price_count: int = 0
    release_date_count: int = 0
    linked_order_id: int | None = None
    linked_import_id: int | None = None
    inventory_copies_created: int | None = None
    total_ordered_quantity: int | None = None
    portfolio_items_added: int | None = None
    enrichment_summary: dict | None = None
    materialization_line_debug: list[dict] = Field(default_factory=list)
    capture_quality_summary_json: dict = Field(default_factory=dict)
    parser_quality_summary_json: dict = Field(default_factory=dict)
    raw_fields_summary_json: dict = Field(default_factory=dict)
    updated_at: datetime
    items: list[RetailerOrderItemSnapshotRead] = Field(default_factory=list)


class RetailerOrderLineDiagnostic(BaseModel):
    line_index: int
    raw_title: str | None = None
    series_search_title: str | None = None
    normalized_title: str | None = None
    parsed_issue_number: str | None = None
    parsed_cover_name: str | None = None
    candidate_count: int = 0
    matched: bool = False
    catalog_match_id: int | None = None
    match_score: int | None = None
    chosen_source: str | None = None
    rejection_reason: str | None = None
    release_date: str | None = None
    foc_date: str | None = None
    cover_image_url: str | None = None
    enrichment_status: str | None = None
    top_candidates: list[dict] = Field(default_factory=list)


class RetailerOrderReEnrichResponse(BaseModel):
    order_id: int
    linked_order_id: int | None = None
    enrichment_summary: dict
    lines: list[RetailerOrderLineDiagnostic] = Field(default_factory=list)


class RetailerAccountSyncRequest(BaseModel):
    limit_orders: int = Field(default=25, ge=1, le=100)


class RetailerLocalSyncStartRequest(BaseModel):
    limit_orders: int = Field(default=25, ge=1, le=100)


class RetailerLocalSyncDetailPageCapture(BaseModel):
    detail_url: str = Field(min_length=1, max_length=2048)
    html: str = Field(min_length=1)
    retailer_order_number: str | None = Field(default=None, max_length=128)
    fallback_order_number: str | None = Field(default=None, max_length=128)
    capture_diagnostics: dict | None = None


class RetailerLocalSyncCompleteRequest(BaseModel):
    helper_token: str = Field(min_length=1, max_length=512)
    history_html: str = Field(min_length=1)
    detail_pages: list[RetailerLocalSyncDetailPageCapture] = Field(default_factory=list)


class RetailerAccountTestResponse(BaseModel):
    account: RetailerAccountRead
    run: RetailerSyncRunRead


class RetailerLocalSyncStartResponse(BaseModel):
    account: RetailerAccountRead
    run: RetailerSyncRunRead
    helper_token: str
    helper_token_expires_at: datetime
    capture_url: str
    capture_mode: str = "extension"


class RetailerAccountSyncResponse(BaseModel):
    account: RetailerAccountRead
    run: RetailerSyncRunRead
    orders: list[RetailerOrderSnapshotRead] = Field(default_factory=list)


class RetailerAccountsListResponse(BaseModel):
    items: list[RetailerAccountRead] = Field(default_factory=list)


class RetailerSyncRunListResponse(BaseModel):
    items: list[RetailerSyncRunRead] = Field(default_factory=list)


class RetailerOrderListResponse(BaseModel):
    items: list[RetailerOrderSnapshotRead] = Field(default_factory=list)


class MidtownHtmlImportResponse(BaseModel):
    order_id: int
    retailer_order_number: str
    item_count: int


class MidtownHtmlImportDebugResponse(BaseModel):
    title: str | None = None
    page_length: int
    order_item_count: int
    has_right_contents: bool
    has_info_container: bool
    visible_text_excerpt: str


class SupportedRetailerRead(BaseModel):
    key: str
    display_name: str
    status: str
    supported: bool
    accepts_upload: bool
    is_fallback: bool = False


class SupportedRetailersResponse(BaseModel):
    items: list[SupportedRetailerRead] = Field(default_factory=list)


class RetailerHtmlImportResponse(BaseModel):
    order_id: int
    retailer: str
    retailer_order_number: str
    item_count: int
    parser_status: str
    warnings: list[str] = Field(default_factory=list)


class RetailerHtmlImportDebugResponse(BaseModel):
    retailer: str
    title: str | None = None
    page_length: int
    order_item_count: int
    has_right_contents: bool
    has_info_container: bool
    visible_text_excerpt: str


class MidtownHtmlImportDiagnostics(BaseModel):
    title: str | None = None
    page_length: int
    order_item_count: int
    order_number_link_count: int
    visible_text_excerpt: str
    has_right_contents: bool
    has_info_container: bool
    saved_html_path: str | None = None
    parsed: dict | None = None


class MidtownBrowserOrderRead(BaseModel):
    retailer_order_number: str
    order_date: date | None = None
    order_status: str | None = None
    order_total: Decimal | None = None
    item_count: int | None = None
    detail_url: str | None = None


class MidtownBrowserSessionStatusRead(BaseModel):
    retailer: str = "midtown"
    account_id: int
    status: str
    message: str | None = None
    current_url: str | None = None
    orders_url: str
    authenticated: bool = False
    order_count: int = 0
    last_updated_at: datetime | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    live_session_active: bool | None = None
    process_id: int | None = None
    registry_contains_account: bool | None = None
    registry_session_count: int | None = None
    active_element_tag: str | None = None
    active_element_name: str | None = None
    active_element_type: str | None = None
    active_element_placeholder: str | None = None


class MidtownBrowserSessionResponse(BaseModel):
    session: MidtownBrowserSessionStatusRead


class MidtownBrowserOrdersResponse(BaseModel):
    session: MidtownBrowserSessionStatusRead
    orders: list[MidtownBrowserOrderRead] = Field(default_factory=list)


class MidtownBrowserCaptureResponse(BaseModel):
    session: MidtownBrowserSessionStatusRead
    order_id: int
    retailer_order_number: str


class MidtownBrowserFrameResponse(BaseModel):
    session: MidtownBrowserSessionStatusRead
    image_data_url: str
    image_width: int
    image_height: int
    captured_at: datetime
    frame_available: bool | None = None
    endpoint_status: int | None = None
    image_bytes_size: int | None = None
    page_title: str | None = None
    page_url: str | None = None
    browser_exists: bool | None = None
    context_exists: bool | None = None
    page_exists: bool | None = None
    process_id: int | None = None
    registry_contains_account: bool | None = None
    registry_session_count: int | None = None
    active_element_tag: str | None = None
    active_element_name: str | None = None
    active_element_type: str | None = None
    active_element_placeholder: str | None = None


class MidtownBrowserClickRequest(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    button: Literal["left", "right", "middle"] = "left"
    click_count: int = Field(default=1, ge=1, le=2)
    displayed_image_width: int | None = Field(default=None, ge=0)
    displayed_image_height: int | None = Field(default=None, ge=0)
    viewport_width: int | None = Field(default=None, ge=0)
    viewport_height: int | None = Field(default=None, ge=0)


class MidtownBrowserTypeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class MidtownBrowserKeyRequest(BaseModel):
    key: str = Field(min_length=1, max_length=100)
