"""P62 Buy Queue API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class BuyQueueSnapshotRead(BaseModel):
    id: int
    owner_id: int
    snapshot_date: date
    generated_at: datetime
    total_items: int
    metadata_json: dict = Field(default_factory=dict)


class BuyQueueItemRead(BaseModel):
    id: int
    snapshot_id: int
    owner_id: int
    recommendation_id: int | None = None
    release_issue_id: int | None = None
    external_catalog_issue_id: int | None = None
    title: str
    issue_number: str
    publisher: str
    priority_score: float
    recommendation_score: float
    demand_score: float
    velocity_score: float
    spec_score: float
    buy_reason: str
    quantity_recommended: int
    estimated_cost: float
    foc_date: date | None = None
    release_date: date | None = None
    status: str


class BuyQueueListRead(BaseModel):
    snapshot: BuyQueueSnapshotRead | None = None
    items: list[BuyQueueItemRead] = Field(default_factory=list)
    total_items: int = 0
    limit: int = 50
    offset: int = 0


class BuyQueueBuildResultRead(BaseModel):
    snapshot_id: int
    total_items: int


class BuyQueueItemStatusUpdate(BaseModel):
    status: str


class BuyQueueCertificationRead(BaseModel):
    component: str
    certified: bool
    status: str
    summary: str
    notes: list[str] = Field(default_factory=list)
    checked_at: str
