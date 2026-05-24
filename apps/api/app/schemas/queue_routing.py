"""Deterministic queue-routing recommendations (signals only; no auto-enqueue)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QueueRoutingRecommendationType = Literal[
    "recommend_ocr",
    "recommend_high_res_review",
    "recommend_manual_review",
    "recommend_rescan",
    "recommend_hold",
    "recommend_no_action",
]

QueueRoutingPriority = Literal["high", "medium", "low"]
QueueRoutingStatus = Literal["open", "acknowledged", "dismissed", "resolved"]


class QueueRoutingRecommendationRead(BaseModel):
    id: int | None = None
    scan_session_item_id: int | None = None
    cover_image_id: int | None = None
    scan_session_id: int | None = None
    recommendation_type: QueueRoutingRecommendationType
    priority: QueueRoutingPriority
    routing_status: QueueRoutingStatus
    evidence_json: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueueRoutingListResponse(BaseModel):
    items: list[QueueRoutingRecommendationRead] = Field(default_factory=list)
    totals_by_recommendation: dict[str, int] = Field(default_factory=dict)
    totals_by_status: dict[str, int] = Field(default_factory=dict)
    unresolved_count: int = 0


QueueRoutingRecommendationListResponse = QueueRoutingListResponse


class ScanSessionRoutingRead(BaseModel):
    scan_session_id: int
    owner_user_id: int
    persisted_run: bool = False
    items: list[QueueRoutingRecommendationRead] = Field(default_factory=list)
    totals_by_recommendation: dict[str, int] = Field(default_factory=dict)
    totals_by_status: dict[str, int] = Field(default_factory=dict)
    unresolved_count: int = 0

