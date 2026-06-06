"""P74-01 release monitoring API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.release_watchlist import ReleaseWatchlistDetailRead


class P74UpcomingReleaseRowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: int
    publisher: str
    series_name: str
    issue_number: str
    title: str
    release_date: date | None
    variant_count: int
    window: str


class P74UpcomingReleasesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    this_week: list[P74UpcomingReleaseRowRead] = Field(default_factory=list)
    next_week: list[P74UpcomingReleaseRowRead] = Field(default_factory=list)
    next_30_days: list[P74UpcomingReleaseRowRead] = Field(default_factory=list)
    next_90_days: list[P74UpcomingReleaseRowRead] = Field(default_factory=list)
    snapshot_id: int = 0


class P74ReleaseChangeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    issue_id: int | None
    variant_id: int | None
    change_type: str
    before_json: dict
    after_json: dict
    detected_at: datetime


class P74ReleaseChangeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P74ReleaseChangeRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0


class P74ReleaseEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    issue_id: int | None
    variant_id: int | None
    event_type: str
    payload_json: dict
    created_at: datetime


class P74ReleaseEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P74ReleaseEventRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0


class P74DiscoveryHighlightRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    issue_id: int
    publisher: str
    series_name: str
    issue_number: str
    release_date: date | None


class P74VariantChangeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_id: int
    issue_id: int | None
    variant_id: int | None
    variant_name: str
    change_type: str
    detected_at: datetime
    late_added: bool


class P74WatchlistActivityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watchlist_id: int
    watchlist_name: str
    watchlist_type: str
    changes_since_review: int
    recent_events: list[P74ReleaseEventRead] = Field(default_factory=list)


class P74WatchlistMonitoringRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watchlists: list[ReleaseWatchlistDetailRead] = Field(default_factory=list)
    activity: list[P74WatchlistActivityRead] = Field(default_factory=list)
    total_watchlists: int


class P74ReleaseMonitoringDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    generated_at: datetime
    upcoming: P74UpcomingReleasesRead
    recent_changes: list[P74ReleaseChangeRead] = Field(default_factory=list)
    new_number_ones: list[P74DiscoveryHighlightRead] = Field(default_factory=list)
    variant_changes: list[P74VariantChangeRead] = Field(default_factory=list)
    watchlist_activity: list[P74WatchlistActivityRead] = Field(default_factory=list)
