from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

SOURCE_VERSION = "P51-02"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


KEY_ISSUE_TYPES = frozenset(
    {
        "FIRST_APPEARANCE",
        "FIRST_FULL_APPEARANCE",
        "FIRST_CAMEO",
        "FIRST_TEAM_APPEARANCE",
        "FIRST_VILLAIN_APPEARANCE",
        "ORIGIN",
        "DEATH",
        "RESURRECTION",
        "MAJOR_STATUS_CHANGE",
        "MILESTONE_NUMBERING",
        "ANNIVERSARY",
        "LAST_ISSUE",
        "FINAL_STORYLINE",
        "MAJOR_EVENT",
        "UNIVERSE_LAUNCH",
        "RELAUNCH",
    }
)


class KeyIssueProfile(SQLModel, table=True):
    __tablename__ = "key_issue_profile"
    __table_args__ = (
        UniqueConstraint("release_issue_id", "key_issue_type", name="uq_key_issue_profile_issue_type"),
        SAIndex("ix_key_issue_profile_issue_created", "release_issue_id", "created_at", "id"),
        SAIndex("ix_key_issue_profile_type_score", "key_issue_type", "importance_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    key_issue_type: str = Field(max_length=48, nullable=False, index=True)
    importance_score: float = Field(default=0.0, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False)
    source_version: str = Field(default=SOURCE_VERSION, max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class KeyIssueSignal(SQLModel, table=True):
    __tablename__ = "key_issue_signal"
    __table_args__ = (SAIndex("ix_key_issue_signal_issue_type", "release_issue_id", "signal_type", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    signal_type: str = Field(max_length=48, nullable=False, index=True)
    signal_strength: float = Field(default=0.0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class KeyIssueEvidence(SQLModel, table=True):
    __tablename__ = "key_issue_evidence"
    __table_args__ = (SAIndex("ix_key_issue_evidence_profile", "key_issue_profile_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    key_issue_profile_id: int = Field(foreign_key="key_issue_profile.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=48, nullable=False, index=True)
    evidence_value: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class KeyIssueClassification(SQLModel, table=True):
    __tablename__ = "key_issue_classification"
    __table_args__ = (
        UniqueConstraint("release_issue_id", name="uq_key_issue_classification_issue"),
        SAIndex("ix_key_issue_classification_class", "classification", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    classification: str = Field(max_length=48, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
