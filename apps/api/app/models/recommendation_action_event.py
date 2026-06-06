"""P73-01 recommendation action events (append-only audit trail)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P73_EVENT_VIEWED = "VIEWED"
P73_EVENT_PURCHASED = "PURCHASED"
P73_EVENT_SKIPPED = "SKIPPED"
P73_EVENT_WATCHLISTED = "WATCHLISTED"
P73_EVENT_HELD = "HELD"
P73_EVENT_GRADED = "GRADED"
P73_EVENT_LISTED = "LISTED"
P73_EVENT_SOLD = "SOLD"
P73_EVENT_RECOMMENDED = "RECOMMENDED"

P73_ALL_EVENT_TYPES = frozenset(
    {
        P73_EVENT_RECOMMENDED,
        P73_EVENT_VIEWED,
        P73_EVENT_PURCHASED,
        P73_EVENT_SKIPPED,
        P73_EVENT_WATCHLISTED,
        P73_EVENT_HELD,
        P73_EVENT_GRADED,
        P73_EVENT_LISTED,
        P73_EVENT_SOLD,
    }
)

# Higher index = later lifecycle stage for status derivation
P73_EVENT_STAGE_ORDER: dict[str, int] = {
    P73_EVENT_RECOMMENDED: 0,
    P73_EVENT_VIEWED: 1,
    P73_EVENT_SKIPPED: 2,
    P73_EVENT_WATCHLISTED: 2,
    P73_EVENT_PURCHASED: 3,
    P73_EVENT_HELD: 4,
    P73_EVENT_GRADED: 5,
    P73_EVENT_LISTED: 6,
    P73_EVENT_SOLD: 7,
}

P73_ATTRIBUTION_MAP: dict[str, str] = {
    "BUY": P73_EVENT_PURCHASED,
    "BUY_AGGRESSIVE": P73_EVENT_PURCHASED,
    "GRADE": P73_EVENT_GRADED,
    "GRADE_CANDIDATE": P73_EVENT_GRADED,
    "SELL": P73_EVENT_SOLD,
    "SELL_NOW": P73_EVENT_SOLD,
    "FLIP": P73_EVENT_SOLD,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P73RecommendationActionEvent(SQLModel, table=True):
    __tablename__ = "p73_recommendation_action_event"
    __table_args__ = (
        SAIndex("ix_p73_rec_event_outcome_created", "outcome_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    outcome_id: int = Field(foreign_key="p73_recommendation_outcome.id", nullable=False, index=True)
    event_type: str = Field(max_length=32, nullable=False, index=True)
    event_source: str = Field(default="manual", max_length=32, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
