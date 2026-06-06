"""P79-03 storage analytics API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class P79StorageAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    generated_at: datetime
    total_locations: int
    total_boxes: int
    total_capacity: int
    used_capacity: int
    available_capacity: int
    utilization_pct: float
    assigned_inventory_count: int
    unassigned_inventory_count: int
    over_capacity_boxes: int
    inactive_locations: int
    forecast_risk: str
    estimated_months_until_full: float | None = None


class P79UtilizationRowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_kind: str
    group_key: str
    entity_id: int | None = None
    utilization_pct: float
    used_capacity: int
    total_capacity: int


class P79StorageUtilizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    items: list[P79UtilizationRowRead] = Field(default_factory=list)


class P79StorageAuditAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    audits_started: int
    audits_completed: int
    average_verification_rate_pct: float
    missing_books_found: int
    unexpected_books_found: int
    duplicate_assignments_found: int
    moved_books: int
    audit_accuracy_rate_pct: float


class P79UnassignedInventoryRowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    title: str
    in_hand: bool
    graded: bool
    sell_queue: bool
    high_value: bool
    estimated_fmv: Decimal | None = None


class P79UnassignedInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_unassigned: int
    in_hand_unassigned: int
    graded_unassigned: int
    sell_queue_unassigned: int
    high_value_unassigned: int
    items: list[P79UnassignedInventoryRowRead] = Field(default_factory=list)


class P79StorageHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    health_score: int
    health_status: str
    factors: dict[str, float | int] = Field(default_factory=dict)


class P79StorageCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    passed: bool
    detail: str


class P79StorageCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_for_production: bool
    checks: list[P79StorageCertificationCheckRead]
    platform_status: str
    reviewed_at: datetime


class P79StorageAnalyticsDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    generated_at: datetime
    analytics: P79StorageAnalyticsRead
    health: P79StorageHealthRead
    utilization: list[P79UtilizationRowRead] = Field(default_factory=list)
    audit_analytics: P79StorageAuditAnalyticsRead
    unassigned: P79UnassignedInventoryResponse
    over_capacity_alerts: list[P79UtilizationRowRead] = Field(default_factory=list)
    certification_status: str = "APPROVED_FOR_PRODUCTION"
