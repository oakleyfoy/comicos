"""add automation rules engine

Revision ID: 20260622_0110
Revises: 20260621_0109
Create Date: 2026-06-22 00:11:10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260622_0110"
down_revision = "20260621_0109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("rule_key", sa.String(length=160), nullable=False),
        sa.Column("rule_name", sa.String(length=200), nullable=False),
        sa.Column("rule_category", sa.String(length=32), nullable=False),
        sa.Column("rule_status", sa.String(length=24), nullable=False),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("deterministic_ordering_enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "rule_key", name="uq_automation_rule_owner_key"),
    )
    op.create_index("ix_automation_rule_status_created", "automation_rules", ["rule_status", "created_at", "id"])
    op.create_index("ix_automation_rule_category_created", "automation_rules", ["rule_category", "created_at", "id"])

    op.create_table(
        "automation_rule_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_status", sa.String(length=24), nullable=False),
        sa.Column("condition_expression", sa.String(length=2048), nullable=False),
        sa.Column("action_definition_json", sa.JSON(), nullable=False),
        sa.Column("evaluation_scope", sa.String(length=80), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("version_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "version_number", name="uq_automation_rule_version_rule_number"),
        sa.UniqueConstraint("version_checksum", name="uq_automation_rule_version_checksum"),
    )
    op.create_index("ix_automation_rule_version_rule_created", "automation_rule_versions", ["rule_id", "created_at", "id"])
    op.create_index("ix_automation_rule_version_status_created", "automation_rule_versions", ["version_status", "created_at", "id"])
    op.create_foreign_key(
        "fk_automation_rules_current_version_id",
        "automation_rules",
        "automation_rule_versions",
        ["current_version_id"],
        ["id"],
    )

    op.create_table(
        "automation_rule_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("rule_version_id", sa.Integer(), nullable=False),
        sa.Column("evaluation_type", sa.String(length=32), nullable=False),
        sa.Column("evaluation_status", sa.String(length=24), nullable=False),
        sa.Column("evaluation_scope", sa.String(length=80), nullable=False),
        sa.Column("evaluation_input_json", sa.JSON(), nullable=False),
        sa.Column("evaluation_result_json", sa.JSON(), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("evaluation_rank", sa.Integer(), nullable=False),
        sa.Column("evaluation_checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"]),
        sa.ForeignKeyConstraint(["rule_version_id"], ["automation_rule_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_version_id", "evaluation_checksum", name="uq_automation_rule_eval_version_checksum"),
    )
    op.create_index("ix_automation_rule_eval_rule_created", "automation_rule_evaluations", ["rule_id", "created_at", "id"])
    op.create_index("ix_automation_rule_eval_status_created", "automation_rule_evaluations", ["evaluation_status", "created_at", "id"])
    op.create_index("ix_automation_rule_eval_type_rank", "automation_rule_evaluations", ["evaluation_type", "evaluation_rank", "created_at", "id"])

    op.create_table(
        "automation_rule_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("action_status", sa.String(length=24), nullable=False),
        sa.Column("action_rank", sa.Integer(), nullable=False),
        sa.Column("target_scope", sa.String(length=120), nullable=False),
        sa.Column("action_payload_json", sa.JSON(), nullable=False),
        sa.Column("action_checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_id"], ["automation_rule_evaluations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", "action_rank", "action_type", name="uq_automation_rule_action_eval_rank_type"),
        sa.UniqueConstraint("action_checksum", name="uq_automation_rule_action_checksum"),
    )
    op.create_index("ix_automation_rule_action_eval_created", "automation_rule_actions", ["evaluation_id", "created_at", "id"])
    op.create_index("ix_automation_rule_action_status_created", "automation_rule_actions", ["action_status", "created_at", "id"])

    op.create_table(
        "automation_rule_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_id"], ["automation_rule_evaluations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", "artifact_type", "artifact_checksum", name="uq_automation_rule_artifact_eval_type_checksum"),
    )
    op.create_index("ix_automation_rule_artifact_eval_created", "automation_rule_artifacts", ["evaluation_id", "created_at", "id"])

    op.create_table(
        "automation_rule_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("rule_version_id", sa.Integer(), nullable=True),
        sa.Column("evaluation_id", sa.Integer(), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_id"], ["automation_rule_evaluations.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"]),
        sa.ForeignKeyConstraint(["rule_version_id"], ["automation_rule_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", "issue_checksum", name="uq_automation_rule_issue_eval_checksum"),
    )
    op.create_index("ix_automation_rule_issue_type_created", "automation_rule_issues", ["issue_type", "created_at", "id"])
    op.create_index("ix_automation_rule_issue_eval_created", "automation_rule_issues", ["evaluation_id", "created_at", "id"])

    op.create_table(
        "automation_rule_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("rule_version_id", sa.Integer(), nullable=True),
        sa.Column("evaluation_id", sa.Integer(), nullable=True),
        sa.Column("action_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["automation_rule_actions.id"]),
        sa.ForeignKeyConstraint(["evaluation_id"], ["automation_rule_evaluations.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"]),
        sa.ForeignKeyConstraint(["rule_version_id"], ["automation_rule_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "event_checksum", name="uq_automation_rule_history_rule_checksum"),
    )
    op.create_index("ix_automation_rule_history_rule_created", "automation_rule_history", ["rule_id", "created_at", "id"])
    op.create_index("ix_automation_rule_history_type_created", "automation_rule_history", ["event_type", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("automation_rule_history")
    op.drop_table("automation_rule_issues")
    op.drop_table("automation_rule_artifacts")
    op.drop_table("automation_rule_actions")
    op.drop_table("automation_rule_evaluations")
    op.drop_constraint("fk_automation_rules_current_version_id", "automation_rules", type_="foreignkey")
    op.drop_table("automation_rule_versions")
    op.drop_table("automation_rules")
