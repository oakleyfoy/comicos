"""add ops dashboard engine

Revision ID: 20260621_0109
Revises: 20260620_0108
Create Date: 2026-06-21 00:10:09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260621_0109"
down_revision = "20260620_0108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_ops_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_key", sa.String(length=160), nullable=False),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
        sa.Column("snapshot_status", sa.String(length=16), nullable=False),
        sa.Column("queue_depth", sa.Integer(), nullable=False),
        sa.Column("active_workers", sa.Integer(), nullable=False),
        sa.Column("active_workflows", sa.Integer(), nullable=False),
        sa.Column("failed_jobs", sa.Integer(), nullable=False),
        sa.Column("dead_letter_count", sa.Integer(), nullable=False),
        sa.Column("replay_warning_count", sa.Integer(), nullable=False),
        sa.Column("checksum_warning_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_manifest_json", sa.JSON(), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "snapshot_key", name="uq_automation_ops_snapshot_owner_key"),
    )
    op.create_index(
        "ix_automation_ops_snapshot_type_created",
        "automation_ops_snapshots",
        ["snapshot_type", "created_at", "id"],
    )
    op.create_index(
        "ix_automation_ops_snapshot_status_created",
        "automation_ops_snapshots",
        ["snapshot_status", "created_at", "id"],
    )

    op.create_table(
        "automation_ops_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("metric_category", sa.String(length=24), nullable=False),
        sa.Column("metric_value", sa.String(length=512), nullable=False),
        sa.Column("metric_status", sa.String(length=16), nullable=False),
        sa.Column("metric_rank", sa.Integer(), nullable=False),
        sa.Column("metric_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_ops_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "metric_key", name="uq_automation_ops_metric_snapshot_key"),
    )
    op.create_index(
        "ix_automation_ops_metric_category_rank",
        "automation_ops_metrics",
        ["snapshot_id", "metric_category", "metric_rank", "metric_key", "id"],
    )

    op.create_table(
        "automation_ops_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("audit_key", sa.String(length=160), nullable=False),
        sa.Column("audit_type", sa.String(length=32), nullable=False),
        sa.Column("audit_status", sa.String(length=16), nullable=False),
        sa.Column("audit_scope", sa.String(length=80), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("audit_checksum", sa.String(length=64), nullable=False),
        sa.Column("audit_result_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_ops_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_key", name="uq_automation_ops_audit_key"),
    )
    op.create_index("ix_automation_ops_audit_type_created", "automation_ops_audits", ["audit_type", "created_at", "id"])
    op.create_index("ix_automation_ops_audit_status_created", "automation_ops_audits", ["audit_status", "created_at", "id"])

    op.create_table(
        "automation_ops_controls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("control_key", sa.String(length=160), nullable=False),
        sa.Column("control_type", sa.String(length=32), nullable=False),
        sa.Column("control_status", sa.String(length=16), nullable=False),
        sa.Column("target_scope", sa.String(length=80), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("control_checksum", sa.String(length=64), nullable=False),
        sa.Column("control_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_ops_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("control_key", name="uq_automation_ops_control_key"),
    )
    op.create_index(
        "ix_automation_ops_control_type_created",
        "automation_ops_controls",
        ["control_type", "created_at", "id"],
    )
    op.create_index(
        "ix_automation_ops_control_status_created",
        "automation_ops_controls",
        ["control_status", "created_at", "id"],
    )

    op.create_table(
        "automation_ops_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("audit_id", sa.Integer(), nullable=True),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["automation_ops_audits.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_ops_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_automation_ops_artifact_type_checksum",
        ),
    )
    op.create_index(
        "ix_automation_ops_artifact_snapshot_created",
        "automation_ops_artifacts",
        ["snapshot_id", "created_at", "id"],
    )

    op.create_table(
        "automation_ops_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_ops_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "issue_checksum", name="uq_automation_ops_issue_checksum"),
    )
    op.create_index("ix_automation_ops_issue_type_created", "automation_ops_issues", ["issue_type", "created_at", "id"])
    op.create_index(
        "ix_automation_ops_issue_snapshot_created",
        "automation_ops_issues",
        ["snapshot_id", "created_at", "id"],
    )

    op.create_table(
        "automation_ops_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("audit_id", sa.Integer(), nullable=True),
        sa.Column("control_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["automation_ops_audits.id"]),
        sa.ForeignKeyConstraint(["control_id"], ["automation_ops_controls.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_ops_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "event_checksum", name="uq_automation_ops_history_checksum"),
    )
    op.create_index(
        "ix_automation_ops_history_snapshot_created",
        "automation_ops_history",
        ["snapshot_id", "created_at", "id"],
    )
    op.create_index("ix_automation_ops_history_type_created", "automation_ops_history", ["event_type", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("automation_ops_history")
    op.drop_table("automation_ops_issues")
    op.drop_table("automation_ops_artifacts")
    op.drop_table("automation_ops_controls")
    op.drop_table("automation_ops_audits")
    op.drop_table("automation_ops_metrics")
    op.drop_table("automation_ops_snapshots")
