"""P80-04 mobile scanning platform certification schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class P80MobileCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    component: str
    passed: bool
    detail: str = ""
    warning: bool = False
    duration_ms: float | None = None


class P80MobileCertificationCategoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    passed: bool
    checks_passed: int
    checks_total: int
    failures: int
    warnings: int


class P80MobileCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_status: str
    approved_for_production: bool
    checks_passed: int
    warnings: int
    failures: int
    platform_readiness_percent: float
    categories: list[P80MobileCertificationCategoryRead] = Field(default_factory=list)
    checks: list[P80MobileCertificationCheckRead] = Field(default_factory=list)
    failure_messages: list[str] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)
    reviewed_at: datetime


class P80MobileCertificationChecklistItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: str
    status: str


class P80MobilePerformanceTargetRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    target_ms: float
    observed_ms: float | None
    met: bool


class P80MobileCertificationDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_status: str
    platform_readiness_percent: float
    checks_passed: int
    warnings: int
    failures: int
    category_summary: list[P80MobileCertificationCategoryRead] = Field(default_factory=list)
    performance_targets: list[P80MobilePerformanceTargetRead] = Field(default_factory=list)
    production_checklist: list[P80MobileCertificationChecklistItemRead] = Field(default_factory=list)
    reviewed_at: datetime
