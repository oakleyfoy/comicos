"""P91-01 collector onboarding wizard schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.p77_collector_profile import CollectorType, RiskProfile, TimeHorizon

InterestOptionKind = Literal["PUBLISHER", "CHARACTER", "CREATOR"]


class P91InterestOptionRead(BaseModel):
    label: str
    subtitle: str | None = None
    source_id: int | None = None


class P91InterestOptionListResponse(BaseModel):
    items: list[P91InterestOptionRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int
    query: str = ""


class P91OnboardingDraft(BaseModel):
    step: int = Field(default=1, ge=1, le=99)
    collector_type: CollectorType | None = None
    risk_profile: RiskProfile | None = None
    time_horizon: TimeHorizon | None = None
    publisher_labels: list[str] = Field(default_factory=list)
    character_labels: list[str] = Field(default_factory=list)
    creator_labels: list[str] = Field(default_factory=list)


class P91OnboardingStatusRead(BaseModel):
    onboarding_completed: bool
    onboarding_completed_at: datetime | None = None
    draft: P91OnboardingDraft


class P91OnboardingDraftUpdate(BaseModel):
    draft: P91OnboardingDraft


class P91OnboardingCompleteRequest(BaseModel):
    draft: P91OnboardingDraft | None = None


class P91RecommendationPreviewItem(BaseModel):
    text: str


class P91RecommendationPreviewRead(BaseModel):
    summary: dict[str, str | list[str]]
    priorities: list[P91RecommendationPreviewItem] = Field(default_factory=list)
