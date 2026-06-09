"""P92 guided import API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GuidedImportProgressPhaseRead(BaseModel):
    code: str
    label: str
    complete: bool = False
    active: bool = False


class GuidedImportProgressRead(BaseModel):
    engine_state: str
    user_label: str
    phases: list[GuidedImportProgressPhaseRead] = Field(default_factory=list)
    import_id: int | None = None
    job_status: str = ""
    error: str | None = None


class GuidedImportExceptionItemRead(BaseModel):
    item_index: int
    title: str
    issue_number: str = ""
    publisher: str = ""
    variant_label: str = ""
    release_date: str = ""
    cover_url: str | None = None
    problems: list[str] = Field(default_factory=list)
    cover_source: str | None = None
    cover_confidence: float | None = None
    variant_confidence: float | None = None
    catalog_match_score: int | None = None
    suggested_catalog_title: str | None = None


class GuidedImportReviewRead(BaseModel):
    import_id: int
    auto_matched_count: int
    exception_count: int
    exceptions: list[GuidedImportExceptionItemRead] = Field(default_factory=list)
    status: str


class GuidedImportSummaryRead(BaseModel):
    import_id: int
    books_imported: int
    publisher_count: int
    variant_count: int
    value_tracked: float
    new_series_count: int
    retailer: str | None = None
    order_date: str | None = None


class GuidedImportSuccessRead(BaseModel):
    import_id: int
    books_added: int
    estimated_value: float
    series_discovered: int
    publishers_discovered: int
