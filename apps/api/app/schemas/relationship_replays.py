from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RelationshipReplayType = Literal[
    "link_decisions",
    "relationship_graph",
    "duplicate_scan",
    "variant_family",
    "canonical_issue_suggestions",
    "relationship_conflicts",
    "full_relationship_pipeline",
]
RelationshipReplayRunStatus = Literal[
    "pending",
    "running",
    "completed",
    "completed_with_changes",
    "failed",
    "cancelled",
]
RelationshipReplayItemStatus = Literal["pending", "running", "unchanged", "changed", "failed", "cancelled"]


class RelationshipReplayCreatePayload(BaseModel):
    replay_type: RelationshipReplayType
    cover_image_ids: list[int] = Field(default_factory=list)


class RelationshipReplayItemRead(BaseModel):
    id: int
    replay_run_id: int
    cover_image_id: int | None = None
    relationship_key: str | None = None
    status: RelationshipReplayItemStatus
    previous_snapshot_json: dict = Field(default_factory=dict)
    replay_snapshot_json: dict = Field(default_factory=dict)
    diff_summary_json: dict = Field(default_factory=dict)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class RelationshipReplayRunRead(BaseModel):
    id: int
    replay_type: RelationshipReplayType
    status: RelationshipReplayRunStatus
    total_items: int = 0
    changed_items: int = 0
    unchanged_items: int = 0
    failed_items: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: int | None = None
    replay_version: str
    items: list[RelationshipReplayItemRead] = Field(default_factory=list)
