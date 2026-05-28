from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationRule(SQLModel, table=True):
    __tablename__ = "automation_rules"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "rule_key", name="uq_automation_rule_owner_key"),
        SAIndex("ix_automation_rule_status_created", "rule_status", "created_at", "id"),
        SAIndex("ix_automation_rule_category_created", "rule_category", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    rule_key: str = Field(max_length=160, nullable=False, index=True)
    rule_name: str = Field(max_length=200, nullable=False)
    rule_category: str = Field(max_length=32, nullable=False, index=True)
    rule_status: str = Field(max_length=24, nullable=False, index=True)
    current_version_id: int | None = Field(default=None, foreign_key="automation_rule_versions.id", nullable=True, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    deterministic_ordering_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRuleVersion(SQLModel, table=True):
    __tablename__ = "automation_rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_id", "version_number", name="uq_automation_rule_version_rule_number"),
        UniqueConstraint("version_checksum", name="uq_automation_rule_version_checksum"),
        SAIndex("ix_automation_rule_version_rule_created", "rule_id", "created_at", "id"),
        SAIndex("ix_automation_rule_version_status_created", "version_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="automation_rules.id", nullable=False, index=True)
    version_number: int = Field(nullable=False, index=True)
    version_status: str = Field(max_length=24, nullable=False, index=True)
    condition_expression: str = Field(max_length=2048, nullable=False)
    action_definition_json: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    evaluation_scope: str = Field(max_length=80, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    version_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRuleEvaluation(SQLModel, table=True):
    __tablename__ = "automation_rule_evaluations"
    __table_args__ = (
        UniqueConstraint("rule_version_id", "evaluation_checksum", name="uq_automation_rule_eval_version_checksum"),
        SAIndex("ix_automation_rule_eval_rule_created", "rule_id", "created_at", "id"),
        SAIndex("ix_automation_rule_eval_status_created", "evaluation_status", "created_at", "id"),
        SAIndex("ix_automation_rule_eval_type_rank", "evaluation_type", "evaluation_rank", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="automation_rules.id", nullable=False, index=True)
    rule_version_id: int = Field(foreign_key="automation_rule_versions.id", nullable=False, index=True)
    evaluation_type: str = Field(max_length=32, nullable=False, index=True)
    evaluation_status: str = Field(max_length=24, nullable=False, index=True)
    evaluation_scope: str = Field(max_length=80, nullable=False, index=True)
    evaluation_input_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evaluation_result_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    matched: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    evaluation_rank: int = Field(nullable=False, index=True)
    evaluation_checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRuleAction(SQLModel, table=True):
    __tablename__ = "automation_rule_actions"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "action_rank", "action_type", name="uq_automation_rule_action_eval_rank_type"),
        UniqueConstraint("action_checksum", name="uq_automation_rule_action_checksum"),
        SAIndex("ix_automation_rule_action_eval_created", "evaluation_id", "created_at", "id"),
        SAIndex("ix_automation_rule_action_status_created", "action_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    evaluation_id: int = Field(foreign_key="automation_rule_evaluations.id", nullable=False, index=True)
    action_type: str = Field(max_length=32, nullable=False, index=True)
    action_status: str = Field(max_length=24, nullable=False, index=True)
    action_rank: int = Field(nullable=False, index=True)
    target_scope: str = Field(max_length=120, nullable=False, index=True)
    action_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    action_checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRuleArtifact(SQLModel, table=True):
    __tablename__ = "automation_rule_artifacts"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "artifact_type", "artifact_checksum", name="uq_automation_rule_artifact_eval_type_checksum"),
        SAIndex("ix_automation_rule_artifact_eval_created", "evaluation_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    evaluation_id: int = Field(foreign_key="automation_rule_evaluations.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRuleIssue(SQLModel, table=True):
    __tablename__ = "automation_rule_issues"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "issue_checksum", name="uq_automation_rule_issue_eval_checksum"),
        SAIndex("ix_automation_rule_issue_type_created", "issue_type", "created_at", "id"),
        SAIndex("ix_automation_rule_issue_eval_created", "evaluation_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="automation_rules.id", nullable=False, index=True)
    rule_version_id: int | None = Field(default=None, foreign_key="automation_rule_versions.id", nullable=True, index=True)
    evaluation_id: int | None = Field(default=None, foreign_key="automation_rule_evaluations.id", nullable=True, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRuleHistory(SQLModel, table=True):
    __tablename__ = "automation_rule_history"
    __table_args__ = (
        UniqueConstraint("rule_id", "event_checksum", name="uq_automation_rule_history_rule_checksum"),
        SAIndex("ix_automation_rule_history_rule_created", "rule_id", "created_at", "id"),
        SAIndex("ix_automation_rule_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="automation_rules.id", nullable=False, index=True)
    rule_version_id: int | None = Field(default=None, foreign_key="automation_rule_versions.id", nullable=True, index=True)
    evaluation_id: int | None = Field(default=None, foreign_key="automation_rule_evaluations.id", nullable=True, index=True)
    action_id: int | None = Field(default=None, foreign_key="automation_rule_actions.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
