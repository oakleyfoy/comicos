"""add marketplace publish engine

Revision ID: 20260729_0147
Revises: 20260728_0146
Create Date: 2026-07-29 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260729_0147"
down_revision = "20260728_0146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_publish_job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("job_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_uuid", name="uq_marketplace_publish_job_uuid"),
    )
    op.create_index("ix_marketplace_publish_job_job_uuid", "marketplace_publish_job", ["job_uuid"])
    op.create_index("ix_marketplace_publish_job_created_at", "marketplace_publish_job", ["created_at"])
    op.create_index(op.f("ix_marketplace_publish_job_owner_id"), "marketplace_publish_job", ["owner_id"])
    op.create_index(op.f("ix_marketplace_publish_job_listing_id"), "marketplace_publish_job", ["listing_id"])
    op.create_index(op.f("ix_marketplace_publish_job_status"), "marketplace_publish_job", ["status"])
    op.create_index(op.f("ix_marketplace_publish_job_requested_by"), "marketplace_publish_job", ["requested_by"])

    op.create_table(
        "marketplace_publish_target",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("publish_job_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("listing_mapping_id", sa.Integer(), nullable=True),
        sa.Column("target_status", sa.String(length=24), nullable=False),
        sa.Column("planned_payload_json", sa.JSON(), nullable=False),
        sa.Column("result_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_mapping_id"], ["marketplace_listing_mapping.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_account.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.ForeignKeyConstraint(["publish_job_id"], ["marketplace_publish_job.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_publish_target_created_at", "marketplace_publish_target", ["created_at"])
    op.create_index(op.f("ix_marketplace_publish_target_publish_job_id"), "marketplace_publish_target", ["publish_job_id"])
    op.create_index(op.f("ix_marketplace_publish_target_marketplace_id"), "marketplace_publish_target", ["marketplace_id"])
    op.create_index(op.f("ix_marketplace_publish_target_marketplace_account_id"), "marketplace_publish_target", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_publish_target_listing_mapping_id"), "marketplace_publish_target", ["listing_mapping_id"])
    op.create_index(op.f("ix_marketplace_publish_target_target_status"), "marketplace_publish_target", ["target_status"])

    op.create_table(
        "marketplace_publish_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("publish_job_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publish_job_id"], ["marketplace_publish_job.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_publish_event_created_at", "marketplace_publish_event", ["created_at"])
    op.create_index(op.f("ix_marketplace_publish_event_publish_job_id"), "marketplace_publish_event", ["publish_job_id"])

    op.create_table(
        "marketplace_publish_validation_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("publish_job_id", sa.Integer(), nullable=False),
        sa.Column("issue_code", sa.String(length=80), nullable=False),
        sa.Column("issue_message", sa.String(), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publish_job_id"], ["marketplace_publish_job.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_publish_validation_issue_created_at", "marketplace_publish_validation_issue", ["created_at"])
    op.create_index(op.f("ix_marketplace_publish_validation_issue_publish_job_id"), "marketplace_publish_validation_issue", ["publish_job_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_publish_validation_issue_publish_job_id"), table_name="marketplace_publish_validation_issue")
    op.drop_index("ix_marketplace_publish_validation_issue_created_at", table_name="marketplace_publish_validation_issue")
    op.drop_table("marketplace_publish_validation_issue")

    op.drop_index(op.f("ix_marketplace_publish_event_publish_job_id"), table_name="marketplace_publish_event")
    op.drop_index("ix_marketplace_publish_event_created_at", table_name="marketplace_publish_event")
    op.drop_table("marketplace_publish_event")

    op.drop_index(op.f("ix_marketplace_publish_target_target_status"), table_name="marketplace_publish_target")
    op.drop_index(op.f("ix_marketplace_publish_target_listing_mapping_id"), table_name="marketplace_publish_target")
    op.drop_index(op.f("ix_marketplace_publish_target_marketplace_account_id"), table_name="marketplace_publish_target")
    op.drop_index(op.f("ix_marketplace_publish_target_marketplace_id"), table_name="marketplace_publish_target")
    op.drop_index(op.f("ix_marketplace_publish_target_publish_job_id"), table_name="marketplace_publish_target")
    op.drop_index("ix_marketplace_publish_target_created_at", table_name="marketplace_publish_target")
    op.drop_table("marketplace_publish_target")

    op.drop_index(op.f("ix_marketplace_publish_job_requested_by"), table_name="marketplace_publish_job")
    op.drop_index(op.f("ix_marketplace_publish_job_status"), table_name="marketplace_publish_job")
    op.drop_index(op.f("ix_marketplace_publish_job_listing_id"), table_name="marketplace_publish_job")
    op.drop_index(op.f("ix_marketplace_publish_job_owner_id"), table_name="marketplace_publish_job")
    op.drop_index("ix_marketplace_publish_job_created_at", table_name="marketplace_publish_job")
    op.drop_index("ix_marketplace_publish_job_job_uuid", table_name="marketplace_publish_job")
    op.drop_table("marketplace_publish_job")
