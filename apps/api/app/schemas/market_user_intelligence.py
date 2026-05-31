from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MarketDemandEntityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_name: str
    demand_score: float
    confidence_score: float


class MarketDemandListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketDemandEntityRead]
    total_items: int
    limit: int
    offset: int


class UserPreferenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    preference_type: str
    preference_key: str
    preference_label: str
    status: str
    preference_score: float
    confidence_score: float


class UserPreferenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UserPreferenceRead]
    total_items: int
    limit: int
    offset: int


class UserPreferenceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preference_type: str
    preference_label: str
    preference_score: float | None = Field(default=None, ge=0.0, le=100.0)


class UserPreferenceCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preference: UserPreferenceRead


class UserPreferenceDisableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preference: UserPreferenceRead


class PreferenceSignalRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_type: str
    signal_strength: float
    source_type: str
    preference_label: str


class MarketDemandBucketRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str
    count: int


class UpcomingMarketUserFitRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_issue_id: int
    series_name: str
    issue_number: str
    title: str
    release_date: date | None
    combined_market_user_score: float


class MarketUserDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_market_demand: list[MarketDemandEntityRead]
    top_user_preferences: list[UserPreferenceRead]
    preference_signals: list[PreferenceSignalRead]
    market_demand_distribution: list[MarketDemandBucketRead]
    upcoming_high_fit: list[UpcomingMarketUserFitRead]
    total_market_profiles: int
    total_active_preferences: int


class MarketUserRefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: dict[str, int]
    user_preferences: dict[str, int]
