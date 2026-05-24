"""Deterministic collection event timeline (read-only, no pricing or AI summaries)."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.inventory_intelligence import KeyedCount

CollectionTimelineEventType = Literal[
    "inventory_added",
    "preorder_created",
    "release_day",
    "expected_ship_window",
    "inventory_received",
    "scan_completed",
    "ocr_completed",
    "ocr_failed",
    "relationship_reviewed",
    "canonical_suggestion_reviewed",
    "conflict_detected",
    "conflict_resolved",
    "duplicate_detected",
    "variant_family_detected",
]

OwnershipStateFilter = Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"]

CollectionTimelineGrouping = Literal[
    "none",
    "day",
    "week",
    "month",
    "publisher",
    "series",
    "ownership_state",
    "preorder_vs_in_hand",
    "inventory_item",
]

CollectionTimelineSort = Literal["asc", "desc"]


class CollectionTimelineEvent(BaseModel):
    """Single persisted deterministic fact surfaced as a timeline event."""

    stable_id: str = Field(description="Globally stable id derived from backing row + classification.")
    event_type: CollectionTimelineEventType
    occurred_at: datetime

    inventory_copy_id: int
    publisher: str
    series_title: str
    issue_number: str

    ownership_state_snapshot: OwnershipStateFilter = Field(
        description="Ownership normalized from current InventoryCopy/order fields at query time.",
    )
    release_status_snapshot: str
    preorder_track: bool = Field(
        description="True when normalized ownership treats the copy as preorder at query time.",
    )

    evidence_json: dict[str, Any] = Field(default_factory=dict)


class CollectionTimelineEventGroup(BaseModel):
    """Grouped slice of timeline events (ordering preserved within each group)."""

    group_key: str
    events: list[CollectionTimelineEvent]


class CollectionTimelineFiltersEcho(BaseModel):
    event_type: CollectionTimelineEventType | None = None
    publisher: str | None = None
    ownership_state: OwnershipStateFilter | None = None
    release_status: str | None = None
    start_date: date_type | None = None
    end_date: date_type | None = None
    preorder_only: bool = False
    in_hand_only: bool = False
    inventory_copy_id: int | None = None
    grouping: CollectionTimelineGrouping = "none"
    sort: CollectionTimelineSort = "desc"


class CollectionTimelineSummary(BaseModel):
    scope_user_id: int | None = None
    scope: str = Field(description='"owner" or "ops_global".')
    generated_as_of_date: date_type
    total_events_present: int = Field(ge=0, description="Count after filtering, before truncation.")
    truncated_to: int = Field(ge=0, description="Max events returned.")
    earliest_occurrence: datetime | None = None
    latest_occurrence: datetime | None = None
    counts_by_event_type: list[KeyedCount]


class CollectionTimelineEventsResponse(BaseModel):
    scope_user_id: int | None = None
    scope: str = "owner"
    generated_as_of_date: date_type
    summary: CollectionTimelineSummary
    filters: CollectionTimelineFiltersEcho
    events: list[CollectionTimelineEvent] = Field(
        description="Flattened deterministic ordering (within sort directive). Truncated to summary.truncated_to.",
    )
    groups: list[CollectionTimelineEventGroup] = Field(
        default_factory=list,
        description="Used when grouping is not 'none'; each group retains inner sort order.",
    )
