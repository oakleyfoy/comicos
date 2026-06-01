from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.top_spec_pick import TopSpecPickRead


class WeeklySpecDashboardSummaryRead(BaseModel):
    top_picks_count: int = Field(default=0, ge=0)
    preorder_now_count: int = Field(default=0, ge=0)
    average_confidence: float = Field(default=0.0, ge=0.0)
    high_risk_count: int = Field(default=0, ge=0)
    number_one_issues_count: int = Field(default=0, ge=0)
    ratio_variant_count: int = Field(default=0, ge=0)
    first_appearance_count: int = Field(default=0, ge=0)
    foc_approaching_count: int = Field(default=0, ge=0)


class WeeklySpecDashboardItemRead(TopSpecPickRead):
    signal_types: list[str] = Field(default_factory=list)
    foc_urgency_label: str = ""
    future_release_action: str | None = None


class WeeklySpecDashboardRead(BaseModel):
    summary: WeeklySpecDashboardSummaryRead
    publisher_breakdown: dict[str, int] = Field(default_factory=dict)
    signal_breakdown: dict[str, int] = Field(default_factory=dict)
    top_20_preorder: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
    preorder_now: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
    high_confidence: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
    high_risk_high_reward: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
    number_one_issues: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
    ratio_variants: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
    first_appearances: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
    milestones: list[WeeklySpecDashboardItemRead] = Field(default_factory=list)
