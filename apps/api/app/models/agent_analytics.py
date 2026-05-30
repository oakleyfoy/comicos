from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentMetricSnapshot(SQLModel, table=True):
    __tablename__ = "agent_metric_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_uuid", name="uq_agent_metric_snapshot_uuid"),
        SAIndex("ix_agent_metric_snapshot_date_generated", "snapshot_date", "generated_at", "id"),
        SAIndex("ix_agent_metric_snapshot_scope_generated", "scope", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_uuid: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    scope: str = Field(max_length=120, nullable=False)
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AgentPerformanceMetric(SQLModel, table=True):
    __tablename__ = "agent_performance_metric"
    __table_args__ = (
        SAIndex("ix_agent_performance_snapshot_agent", "snapshot_id", "agent_code", "id"),
        SAIndex("ix_agent_performance_agent_created", "agent_code", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="agent_metric_snapshot.id", nullable=False, index=True)
    agent_id: int = Field(foreign_key="agent_definition.id", nullable=False, index=True)
    agent_code: str = Field(max_length=80, nullable=False, index=True)
    executions_total: int = Field(default=0, nullable=False)
    executions_completed: int = Field(default=0, nullable=False)
    executions_failed: int = Field(default=0, nullable=False)
    success_rate: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    failure_rate: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    avg_duration_ms: int | None = Field(default=None, nullable=True)
    last_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_success_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_failure_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    recommendations_generated: int = Field(default=0, nullable=False)
    recommendations_reviewed: int = Field(default=0, nullable=False)
    recommendations_accepted: int = Field(default=0, nullable=False)
    recommendations_dismissed: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class WorkflowPerformanceMetric(SQLModel, table=True):
    __tablename__ = "workflow_performance_metric"
    __table_args__ = (
        SAIndex("ix_workflow_performance_snapshot_workflow", "snapshot_id", "workflow_code", "id"),
        SAIndex("ix_workflow_performance_workflow_created", "workflow_code", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="agent_metric_snapshot.id", nullable=False, index=True)
    workflow_id: int = Field(foreign_key="workflow_definition.id", nullable=False, index=True)
    workflow_code: str = Field(max_length=80, nullable=False, index=True)
    executions_total: int = Field(default=0, nullable=False)
    executions_completed: int = Field(default=0, nullable=False)
    executions_failed: int = Field(default=0, nullable=False)
    success_rate: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    failure_rate: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    avg_duration_ms: int | None = Field(default=None, nullable=True)
    last_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_success_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_failure_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RecommendationOutcomeMetric(SQLModel, table=True):
    __tablename__ = "recommendation_outcome_metric"
    __table_args__ = (
        SAIndex("ix_recommendation_outcome_snapshot_type", "snapshot_id", "recommendation_type", "id"),
        SAIndex("ix_recommendation_outcome_type_created", "recommendation_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="agent_metric_snapshot.id", nullable=False, index=True)
    recommendation_type: str = Field(max_length=80, nullable=False, index=True)
    recommendations_total: int = Field(default=0, nullable=False)
    reviewed_total: int = Field(default=0, nullable=False)
    accepted_total: int = Field(default=0, nullable=False)
    dismissed_total: int = Field(default=0, nullable=False)
    acceptance_rate: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    dismissal_rate: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    avg_confidence_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    avg_opportunity_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    avg_priority_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
