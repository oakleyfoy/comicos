from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReleaseIntelligenceMatch(SQLModel, table=True):
    __tablename__ = "release_intelligence_match"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "release_issue_id",
            "release_variant_id",
            "entity_type",
            "entity_id",
            name="uq_release_intelligence_match",
        ),
        SAIndex("ix_release_intelligence_match_owner_issue", "owner_user_id", "release_issue_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    release_variant_id: int | None = Field(default=None, foreign_key="release_variant.id", nullable=True, index=True)
    entity_type: str = Field(max_length=24, nullable=False, index=True)
    entity_id: int = Field(nullable=False, index=True)
    match_confidence: float = Field(nullable=False)
    match_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
