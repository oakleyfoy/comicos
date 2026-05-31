"""add production readiness certification foundation

Revision ID: 20260807_0156
Revises: 20260806_0155
Create Date: 2026-08-07 01:56:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260807_0156"
down_revision = "20260806_0155"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_readiness_check",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("check_uuid", sa.String(length=64), nullable=False),
        sa.Column("check_name", sa.String(length=120), nullable=False),
        sa.Column("subsystem", sa.String(length=80), nullable=False),
        sa.Column("check_status", sa.String(length=24), nullable=False),
        sa.Column("check_notes", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("check_uuid", name="uq_production_readiness_check_uuid"),
    )
    op.create_index("ix_production_readiness_check_check_uuid", "production_readiness_check", ["check_uuid"])
    op.create_index("ix_production_readiness_check_check_name", "production_readiness_check", ["check_name"])
    op.create_index("ix_production_readiness_check_subsystem", "production_readiness_check", ["subsystem"])
    op.create_index("ix_production_readiness_check_check_status", "production_readiness_check", ["check_status"])
    op.create_index("ix_production_readiness_check_checked_at", "production_readiness_check", ["checked_at"])
    op.create_index(
        "ix_production_readiness_check_subsystem_checked",
        "production_readiness_check",
        ["subsystem", "checked_at", "id"],
    )

    op.create_table(
        "production_certification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("certification_uuid", sa.String(length=64), nullable=False),
        sa.Column("certification_status", sa.String(length=32), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False),
        sa.Column("certification_notes", sa.Text(), nullable=False),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("certification_uuid", name="uq_production_certification_uuid"),
    )
    op.create_index("ix_production_certification_certification_uuid", "production_certification", ["certification_uuid"])
    op.create_index(
        "ix_production_certification_certification_status",
        "production_certification",
        ["certification_status"],
    )
    op.create_index("ix_production_certification_certified_at", "production_certification", ["certified_at"])
    op.create_index(
        "ix_production_certification_status_certified",
        "production_certification",
        ["certification_status", "certified_at", "id"],
    )

    op.create_table(
        "readiness_checklist_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("checklist_category", sa.String(length=80), nullable=False),
        sa.Column("item_name", sa.String(length=120), nullable=False),
        sa.Column("item_status", sa.String(length=24), nullable=False),
        sa.Column("validation_notes", sa.Text(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_readiness_checklist_item_checklist_category", "readiness_checklist_item", ["checklist_category"])
    op.create_index("ix_readiness_checklist_item_item_name", "readiness_checklist_item", ["item_name"])
    op.create_index("ix_readiness_checklist_item_item_status", "readiness_checklist_item", ["item_status"])
    op.create_index("ix_readiness_checklist_item_validated_at", "readiness_checklist_item", ["validated_at"])
    op.create_index(
        "ix_readiness_checklist_category_validated",
        "readiness_checklist_item",
        ["checklist_category", "validated_at", "id"],
    )

    op.create_table(
        "go_live_assessment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_uuid", sa.String(length=64), nullable=False),
        sa.Column("assessment_status", sa.String(length=32), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("assessment_summary", sa.Text(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_uuid", name="uq_go_live_assessment_uuid"),
    )
    op.create_index("ix_go_live_assessment_assessment_uuid", "go_live_assessment", ["assessment_uuid"])
    op.create_index("ix_go_live_assessment_assessment_status", "go_live_assessment", ["assessment_status"])
    op.create_index("ix_go_live_assessment_assessed_at", "go_live_assessment", ["assessed_at"])
    op.create_index(
        "ix_go_live_assessment_status_assessed",
        "go_live_assessment",
        ["assessment_status", "assessed_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_go_live_assessment_status_assessed", table_name="go_live_assessment")
    op.drop_index("ix_go_live_assessment_assessed_at", table_name="go_live_assessment")
    op.drop_index("ix_go_live_assessment_assessment_status", table_name="go_live_assessment")
    op.drop_index("ix_go_live_assessment_assessment_uuid", table_name="go_live_assessment")
    op.drop_table("go_live_assessment")

    op.drop_index("ix_readiness_checklist_category_validated", table_name="readiness_checklist_item")
    op.drop_index("ix_readiness_checklist_item_validated_at", table_name="readiness_checklist_item")
    op.drop_index("ix_readiness_checklist_item_item_status", table_name="readiness_checklist_item")
    op.drop_index("ix_readiness_checklist_item_item_name", table_name="readiness_checklist_item")
    op.drop_index("ix_readiness_checklist_item_checklist_category", table_name="readiness_checklist_item")
    op.drop_table("readiness_checklist_item")

    op.drop_index("ix_production_certification_status_certified", table_name="production_certification")
    op.drop_index("ix_production_certification_certified_at", table_name="production_certification")
    op.drop_index("ix_production_certification_certification_status", table_name="production_certification")
    op.drop_index("ix_production_certification_certification_uuid", table_name="production_certification")
    op.drop_table("production_certification")

    op.drop_index("ix_production_readiness_check_subsystem_checked", table_name="production_readiness_check")
    op.drop_index("ix_production_readiness_check_checked_at", table_name="production_readiness_check")
    op.drop_index("ix_production_readiness_check_check_status", table_name="production_readiness_check")
    op.drop_index("ix_production_readiness_check_subsystem", table_name="production_readiness_check")
    op.drop_index("ix_production_readiness_check_check_name", table_name="production_readiness_check")
    op.drop_index("ix_production_readiness_check_check_uuid", table_name="production_readiness_check")
    op.drop_table("production_readiness_check")
