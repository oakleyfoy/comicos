"""add condition intelligence foundation

Revision ID: 20260808_0157
Revises: 20260807_0156
Create Date: 2026-08-08 01:57:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260808_0157"
down_revision = "20260807_0156"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analysis_uuid", sa.String(length=64), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("front_image_id", sa.Integer(), nullable=True),
        sa.Column("back_image_id", sa.Integer(), nullable=True),
        sa.Column("analysis_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["front_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["back_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_uuid", name="uq_scan_analysis_uuid"),
    )
    op.create_index("ix_scan_analysis_owner_user_id", "scan_analysis", ["owner_user_id"])
    op.create_index("ix_scan_analysis_analysis_uuid", "scan_analysis", ["analysis_uuid"])
    op.create_index("ix_scan_analysis_analysis_status", "scan_analysis", ["analysis_status"])
    op.create_index("ix_scan_analysis_created_at", "scan_analysis", ["created_at"])
    op.create_index("ix_scan_analysis_owner_created", "scan_analysis", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_analysis_status_created", "scan_analysis", ["analysis_status", "created_at", "id"])

    op.create_table(
        "scan_quality_assessment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("image_quality_score", sa.Float(), nullable=False),
        sa.Column("resolution_score", sa.Float(), nullable=False),
        sa.Column("alignment_score", sa.Float(), nullable=False),
        sa.Column("glare_score", sa.Float(), nullable=False),
        sa.Column("crop_score", sa.Float(), nullable=False),
        sa.Column("quality_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_quality_assessment_analysis_id", "scan_quality_assessment", ["analysis_id"])
    op.create_index("ix_scan_quality_assessment_quality_status", "scan_quality_assessment", ["quality_status"])
    op.create_index("ix_scan_quality_assessment_created_at", "scan_quality_assessment", ["created_at"])
    op.create_index(
        "ix_scan_quality_assessment_analysis_created",
        "scan_quality_assessment",
        ["analysis_id", "created_at", "id"],
    )

    op.create_table(
        "condition_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("overall_condition_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_condition_profile_analysis_id", "condition_profile", ["analysis_id"])
    op.create_index("ix_condition_profile_created_at", "condition_profile", ["created_at"])
    op.create_index("ix_condition_profile_analysis_created", "condition_profile", ["analysis_id", "created_at", "id"])

    op.create_table(
        "condition_defect",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("defect_type", sa.String(length=80), nullable=False),
        sa.Column("defect_location", sa.String(length=120), nullable=False),
        sa.Column("defect_severity", sa.String(length=24), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_condition_defect_analysis_id", "condition_defect", ["analysis_id"])
    op.create_index("ix_condition_defect_defect_type", "condition_defect", ["defect_type"])
    op.create_index("ix_condition_defect_created_at", "condition_defect", ["created_at"])
    op.create_index("ix_condition_defect_analysis_created", "condition_defect", ["analysis_id", "created_at", "id"])
    op.create_index("ix_condition_defect_type_created", "condition_defect", ["defect_type", "created_at", "id"])

    op.create_table(
        "condition_subgrade",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("subgrade_type", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_condition_subgrade_analysis_id", "condition_subgrade", ["analysis_id"])
    op.create_index("ix_condition_subgrade_subgrade_type", "condition_subgrade", ["subgrade_type"])
    op.create_index("ix_condition_subgrade_created_at", "condition_subgrade", ["created_at"])
    op.create_index("ix_condition_subgrade_analysis_created", "condition_subgrade", ["analysis_id", "created_at", "id"])
    op.create_index("ix_condition_subgrade_type_created", "condition_subgrade", ["subgrade_type", "created_at", "id"])

    op.create_table(
        "condition_agent_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("agent_code", sa.String(length=80), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_condition_agent_execution_uuid"),
    )
    op.create_index("ix_condition_agent_execution_analysis_id", "condition_agent_execution", ["analysis_id"])
    op.create_index("ix_condition_agent_execution_agent_code", "condition_agent_execution", ["agent_code"])
    op.create_index("ix_condition_agent_execution_execution_uuid", "condition_agent_execution", ["execution_uuid"])
    op.create_index("ix_condition_agent_execution_status", "condition_agent_execution", ["status"])
    op.create_index("ix_condition_agent_execution_created_at", "condition_agent_execution", ["created_at"])
    op.create_index(
        "ix_condition_agent_execution_analysis_started",
        "condition_agent_execution",
        ["analysis_id", "started_at", "id"],
    )
    op.create_index(
        "ix_condition_agent_execution_agent_started",
        "condition_agent_execution",
        ["agent_code", "started_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_condition_agent_execution_agent_started", table_name="condition_agent_execution")
    op.drop_index("ix_condition_agent_execution_analysis_started", table_name="condition_agent_execution")
    op.drop_index("ix_condition_agent_execution_created_at", table_name="condition_agent_execution")
    op.drop_index("ix_condition_agent_execution_status", table_name="condition_agent_execution")
    op.drop_index("ix_condition_agent_execution_execution_uuid", table_name="condition_agent_execution")
    op.drop_index("ix_condition_agent_execution_agent_code", table_name="condition_agent_execution")
    op.drop_index("ix_condition_agent_execution_analysis_id", table_name="condition_agent_execution")
    op.drop_table("condition_agent_execution")

    op.drop_index("ix_condition_subgrade_type_created", table_name="condition_subgrade")
    op.drop_index("ix_condition_subgrade_analysis_created", table_name="condition_subgrade")
    op.drop_index("ix_condition_subgrade_created_at", table_name="condition_subgrade")
    op.drop_index("ix_condition_subgrade_subgrade_type", table_name="condition_subgrade")
    op.drop_index("ix_condition_subgrade_analysis_id", table_name="condition_subgrade")
    op.drop_table("condition_subgrade")

    op.drop_index("ix_condition_defect_type_created", table_name="condition_defect")
    op.drop_index("ix_condition_defect_analysis_created", table_name="condition_defect")
    op.drop_index("ix_condition_defect_created_at", table_name="condition_defect")
    op.drop_index("ix_condition_defect_defect_type", table_name="condition_defect")
    op.drop_index("ix_condition_defect_analysis_id", table_name="condition_defect")
    op.drop_table("condition_defect")

    op.drop_index("ix_condition_profile_analysis_created", table_name="condition_profile")
    op.drop_index("ix_condition_profile_created_at", table_name="condition_profile")
    op.drop_index("ix_condition_profile_analysis_id", table_name="condition_profile")
    op.drop_table("condition_profile")

    op.drop_index("ix_scan_quality_assessment_analysis_created", table_name="scan_quality_assessment")
    op.drop_index("ix_scan_quality_assessment_created_at", table_name="scan_quality_assessment")
    op.drop_index("ix_scan_quality_assessment_quality_status", table_name="scan_quality_assessment")
    op.drop_index("ix_scan_quality_assessment_analysis_id", table_name="scan_quality_assessment")
    op.drop_table("scan_quality_assessment")

    op.drop_index("ix_scan_analysis_status_created", table_name="scan_analysis")
    op.drop_index("ix_scan_analysis_owner_created", table_name="scan_analysis")
    op.drop_index("ix_scan_analysis_created_at", table_name="scan_analysis")
    op.drop_index("ix_scan_analysis_analysis_status", table_name="scan_analysis")
    op.drop_index("ix_scan_analysis_analysis_uuid", table_name="scan_analysis")
    op.drop_index("ix_scan_analysis_owner_user_id", table_name="scan_analysis")
    op.drop_table("scan_analysis")
