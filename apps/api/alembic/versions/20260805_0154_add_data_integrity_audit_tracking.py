"""add data integrity audit tracking

Revision ID: 20260805_0154
Revises: 20260804_0153
Create Date: 2026-08-05 01:54:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260805_0154"
down_revision = "20260804_0153"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_integrity_check",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("check_uuid", sa.String(length=64), nullable=False),
        sa.Column("check_type", sa.String(length=80), nullable=False),
        sa.Column("check_status", sa.String(length=24), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("check_uuid", name="uq_data_integrity_check_uuid"),
    )
    op.create_index("ix_data_integrity_check_owner_user_id", "data_integrity_check", ["owner_user_id"])
    op.create_index("ix_data_integrity_check_check_uuid", "data_integrity_check", ["check_uuid"])
    op.create_index("ix_data_integrity_check_check_type", "data_integrity_check", ["check_type"])
    op.create_index("ix_data_integrity_check_check_status", "data_integrity_check", ["check_status"])
    op.create_index("ix_data_integrity_check_created_at", "data_integrity_check", ["created_at"])
    op.create_index("ix_data_integrity_check_owner_created", "data_integrity_check", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "data_integrity_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("check_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("issue_message", sa.Text(), nullable=False),
        sa.Column("issue_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["check_id"], ["data_integrity_check.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_integrity_issue_check_id", "data_integrity_issue", ["check_id"])
    op.create_index("ix_data_integrity_issue_issue_type", "data_integrity_issue", ["issue_type"])
    op.create_index("ix_data_integrity_issue_severity", "data_integrity_issue", ["severity"])
    op.create_index("ix_data_integrity_issue_entity_type", "data_integrity_issue", ["entity_type"])
    op.create_index("ix_data_integrity_issue_entity_id", "data_integrity_issue", ["entity_id"])
    op.create_index("ix_data_integrity_issue_created_at", "data_integrity_issue", ["created_at"])
    op.create_index("ix_data_integrity_issue_check_created", "data_integrity_issue", ["check_id", "created_at", "id"])

    op.create_table(
        "migration_safety_check",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("migration_revision", sa.String(length=80), nullable=False),
        sa.Column("check_status", sa.String(length=24), nullable=False),
        sa.Column("pre_count_json", sa.JSON(), nullable=False),
        sa.Column("post_count_json", sa.JSON(), nullable=False),
        sa.Column("validation_payload_json", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_migration_safety_check_owner_user_id", "migration_safety_check", ["owner_user_id"])
    op.create_index("ix_migration_safety_check_migration_revision", "migration_safety_check", ["migration_revision"])
    op.create_index("ix_migration_safety_check_check_status", "migration_safety_check", ["check_status"])
    op.create_index("ix_migration_safety_check_created_at", "migration_safety_check", ["created_at"])
    op.create_index("ix_migration_safety_check_owner_created", "migration_safety_check", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("audit_uuid", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.String(length=80), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_uuid", name="uq_audit_event_uuid"),
    )
    op.create_index("ix_audit_event_owner_user_id", "audit_event", ["owner_user_id"])
    op.create_index("ix_audit_event_audit_uuid", "audit_event", ["audit_uuid"])
    op.create_index("ix_audit_event_actor_id", "audit_event", ["actor_id"])
    op.create_index("ix_audit_event_action_type", "audit_event", ["action_type"])
    op.create_index("ix_audit_event_entity_type", "audit_event", ["entity_type"])
    op.create_index("ix_audit_event_entity_id", "audit_event", ["entity_id"])
    op.create_index("ix_audit_event_created_at", "audit_event", ["created_at"])
    op.create_index("ix_audit_event_owner_created", "audit_event", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "change_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_event_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("before_value_json", sa.JSON(), nullable=True),
        sa.Column("after_value_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audit_event_id"], ["audit_event.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_change_record_audit_event_id", "change_record", ["audit_event_id"])
    op.create_index("ix_change_record_field_name", "change_record", ["field_name"])
    op.create_index("ix_change_record_created_at", "change_record", ["created_at"])
    op.create_index("ix_change_record_audit_created", "change_record", ["audit_event_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_change_record_audit_created", table_name="change_record")
    op.drop_index("ix_change_record_created_at", table_name="change_record")
    op.drop_index("ix_change_record_field_name", table_name="change_record")
    op.drop_index("ix_change_record_audit_event_id", table_name="change_record")
    op.drop_table("change_record")

    op.drop_index("ix_audit_event_owner_created", table_name="audit_event")
    op.drop_index("ix_audit_event_created_at", table_name="audit_event")
    op.drop_index("ix_audit_event_entity_id", table_name="audit_event")
    op.drop_index("ix_audit_event_entity_type", table_name="audit_event")
    op.drop_index("ix_audit_event_action_type", table_name="audit_event")
    op.drop_index("ix_audit_event_actor_id", table_name="audit_event")
    op.drop_index("ix_audit_event_audit_uuid", table_name="audit_event")
    op.drop_index("ix_audit_event_owner_user_id", table_name="audit_event")
    op.drop_table("audit_event")

    op.drop_index("ix_migration_safety_check_owner_created", table_name="migration_safety_check")
    op.drop_index("ix_migration_safety_check_created_at", table_name="migration_safety_check")
    op.drop_index("ix_migration_safety_check_check_status", table_name="migration_safety_check")
    op.drop_index("ix_migration_safety_check_migration_revision", table_name="migration_safety_check")
    op.drop_index("ix_migration_safety_check_owner_user_id", table_name="migration_safety_check")
    op.drop_table("migration_safety_check")

    op.drop_index("ix_data_integrity_issue_check_created", table_name="data_integrity_issue")
    op.drop_index("ix_data_integrity_issue_created_at", table_name="data_integrity_issue")
    op.drop_index("ix_data_integrity_issue_entity_id", table_name="data_integrity_issue")
    op.drop_index("ix_data_integrity_issue_entity_type", table_name="data_integrity_issue")
    op.drop_index("ix_data_integrity_issue_severity", table_name="data_integrity_issue")
    op.drop_index("ix_data_integrity_issue_issue_type", table_name="data_integrity_issue")
    op.drop_index("ix_data_integrity_issue_check_id", table_name="data_integrity_issue")
    op.drop_table("data_integrity_issue")

    op.drop_index("ix_data_integrity_check_owner_created", table_name="data_integrity_check")
    op.drop_index("ix_data_integrity_check_created_at", table_name="data_integrity_check")
    op.drop_index("ix_data_integrity_check_check_status", table_name="data_integrity_check")
    op.drop_index("ix_data_integrity_check_check_type", table_name="data_integrity_check")
    op.drop_index("ix_data_integrity_check_check_uuid", table_name="data_integrity_check")
    op.drop_index("ix_data_integrity_check_owner_user_id", table_name="data_integrity_check")
    op.drop_table("data_integrity_check")
