from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.industry_opportunity import IndustryOpportunityRead


class IndustryScannerDashboardSummaryRead(BaseModel):
    releases_scanned: int = Field(default=0, ge=0)
    signals_detected: int = Field(default=0, ge=0)
    high_score_opportunities: int = Field(default=0, ge=0)
    number_one_issues: int = Field(default=0, ge=0)
    ratio_variants: int = Field(default=0, ge=0)
    key_events: int = Field(default=0, ge=0)


class IndustryScannerDashboardItemRead(IndustryOpportunityRead):
    signal_types: list[str] = Field(default_factory=list)
    foc_date: str | None = None
    release_date: str | None = None
    monitoring_status: str = "MONITOR"


class IndustryScannerDashboardRead(BaseModel):
    summary: IndustryScannerDashboardSummaryRead
    scan_run_id: int | None = None
    top_number_one_issues: list[IndustryScannerDashboardItemRead] = Field(default_factory=list)
    ratio_variants: list[IndustryScannerDashboardItemRead] = Field(default_factory=list)
    facsimiles: list[IndustryScannerDashboardItemRead] = Field(default_factory=list)
    anniversary_milestone_books: list[IndustryScannerDashboardItemRead] = Field(default_factory=list)
    key_events: list[IndustryScannerDashboardItemRead] = Field(default_factory=list)
    high_opportunity_score: list[IndustryScannerDashboardItemRead] = Field(default_factory=list)
    watchlist: list[IndustryScannerDashboardItemRead] = Field(default_factory=list)
