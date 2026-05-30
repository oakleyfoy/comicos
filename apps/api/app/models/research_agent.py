from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResearchSnapshot(SQLModel, table=True):
    __tablename__ = "research_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_uuid", name="uq_research_snapshot_uuid"),
        SAIndex("ix_research_snapshot_generated", "generated_at", "id"),
        SAIndex("ix_research_snapshot_agent_generated", "agent_code", "generated_at", "id"),
        SAIndex("ix_research_snapshot_type_generated", "research_type", "generated_at", "id"),
        SAIndex("ix_research_snapshot_status_generated", "status", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    agent_execution_id: int = Field(foreign_key="agent_execution.id", nullable=False, index=True)
    snapshot_uuid: str = Field(max_length=64, nullable=False, index=True)
    agent_code: str = Field(max_length=80, nullable=False, index=True)
    research_type: str = Field(max_length=80, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    input_scope_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ResearchFinding(SQLModel, table=True):
    __tablename__ = "research_finding"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "finding_code", name="uq_research_finding_snapshot_code"),
        SAIndex("ix_research_finding_snapshot_created", "snapshot_id", "created_at", "id"),
        SAIndex("ix_research_finding_type_priority", "finding_type", "priority_score", "id"),
        SAIndex("ix_research_finding_status_priority", "status", "priority_score", "id"),
        SAIndex("ix_research_finding_confidence_priority", "confidence_score", "priority_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="research_snapshot.id", nullable=False, index=True)
    finding_code: str = Field(max_length=120, nullable=False)
    finding_type: str = Field(max_length=80, nullable=False, index=True)
    title: str = Field(max_length=255, nullable=False)
    description: str = Field(max_length=2000, nullable=False)
    confidence_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    priority_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    status: str = Field(default="OPEN", max_length=24, nullable=False, index=True)
    recommendation_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ResearchEvidence(SQLModel, table=True):
    __tablename__ = "research_evidence"
    __table_args__ = (
        SAIndex("ix_research_evidence_finding_created", "finding_id", "created_at", "id"),
        SAIndex("ix_research_evidence_type_score", "evidence_type", "evidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int = Field(foreign_key="research_finding.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=80, nullable=False, index=True)
    source_name: str = Field(max_length=160, nullable=False)
    source_url: str | None = Field(default=None, max_length=1000, nullable=True)
    source_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
