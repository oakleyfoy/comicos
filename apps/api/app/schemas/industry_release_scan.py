from __future__ import annotations

from pydantic import BaseModel, Field


class IndustryReleaseScanRunRead(BaseModel):
    id: int
    owner_id: int
    status: str
    started_at: str
    completed_at: str | None
    releases_scanned: int
    candidates_created: int
    candidates_total: int
    publishers_included: int
    error_message: str
    created_at: str


class IndustryReleaseScanRunListRead(BaseModel):
    items: list[IndustryReleaseScanRunRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class IndustryReleaseCandidateRead(BaseModel):
    id: int
    owner_id: int
    scan_run_id: int
    release_id: int
    publisher_code: str
    publisher_name: str
    series_name: str
    issue_number: str
    foc_date: str | None
    release_date: str | None
    variant_count: int
    monitoring_status: str
    created_at: str


class IndustryReleaseCandidateListRead(BaseModel):
    items: list[IndustryReleaseCandidateRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)
