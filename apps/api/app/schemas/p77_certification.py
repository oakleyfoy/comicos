"""P77-03 collector profile platform certification schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class P77CollectorCertificationCheckRead(BaseModel):
    category: str
    component: str
    passed: bool
    detail: str = ""


class P77CollectorCertificationCategoryRead(BaseModel):
    category: str
    passed: bool
    checks_passed: int
    checks_total: int


class P77CollectorCertificationRead(BaseModel):
    platform_status: str
    approved_for_production: bool
    checks_passed: int
    warnings: int
    failures: int
    platform_readiness_percent: float
    categories: list[P77CollectorCertificationCategoryRead] = Field(default_factory=list)
    checks: list[P77CollectorCertificationCheckRead] = Field(default_factory=list)
    failure_messages: list[str] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)
    production_checklist: list[dict[str, str]] = Field(default_factory=list)
    reviewed_at: datetime
