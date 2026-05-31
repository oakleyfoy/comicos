from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.release_intelligence import ReleaseIssueRead


class CollectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    publisher: str
    series_name: str
    first_issue_owned: str
    latest_issue_owned: str
    issue_count_owned: int
    continuity_status: str
    created_at: datetime


class CollectionContinuityAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    release_issue_id: int
    alert_type: str
    alert_status: str
    alert_payload_json: dict[str, object]
    created_at: datetime


class ReleaseWatchlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    watchlist_name: str
    watchlist_type: str
    created_at: datetime


class ReleaseWatchlistItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    watchlist_id: int
    publisher: str | None
    series_name: str | None
    character_name: str | None
    creator_name: str | None
    keyword: str | None
    created_at: datetime


class ReleaseReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    release_issue_id: int
    reminder_type: str
    reminder_date: date
    reminder_status: str
    created_at: datetime


class WatchlistAgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class ReleaseWatchlistCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watchlist_name: str
    watchlist_type: str


class ReleaseWatchlistItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publisher: str | None = None
    series_name: str | None = None
    character_name: str | None = None
    creator_name: str | None = None
    keyword: str | None = None


class DeleteWatchlistItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int
    deleted: bool


class CollectionRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CollectionRunRead]
    total_items: int
    limit: int
    offset: int


class CollectionContinuityAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CollectionContinuityAlertRead]
    total_items: int
    limit: int
    offset: int


class ReleaseReminderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseReminderRead]
    total_items: int
    limit: int
    offset: int


class ReleaseWatchlistDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watchlist: ReleaseWatchlistRead
    items: list[ReleaseWatchlistItemRead] = Field(default_factory=list)


class ReleaseWatchlistListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReleaseWatchlistDetailRead]
    total_items: int
    limit: int
    offset: int


class WatchlistAgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WatchlistAgentExecutionRead]
    total_items: int
    limit: int
    offset: int


class WatchlistMatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watchlist: ReleaseWatchlistRead
    item: ReleaseWatchlistItemRead
    release_issue: ReleaseIssueRead


class ContinuityDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_runs: list[CollectionRunRead]
    continuity_alerts: list[CollectionContinuityAlertRead]
    foc_reminders: list[ReleaseReminderRead]
    release_reminders: list[ReleaseReminderRead]
    watchlists: list[ReleaseWatchlistDetailRead]
    watchlist_matches: list[WatchlistMatchRead]
    upcoming_watched_releases: list[ReleaseIssueRead]
    agent_activity: list[WatchlistAgentExecutionRead]


class WatchlistAlertsRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[CollectionRunRead]
    alerts: list[CollectionContinuityAlertRead]
    execution: WatchlistAgentExecutionRead


class WatchlistRemindersRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminders: list[ReleaseReminderRead]
    execution: WatchlistAgentExecutionRead


class AutoWatchlistsRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watchlists: list[ReleaseWatchlistDetailRead]
    execution: WatchlistAgentExecutionRead
