"""add research marketplace agents

Revision ID: 20260723_0141
Revises: 20260722_0140
Create Date: 2026-07-23 00:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260723_0141"
down_revision = "20260722_0140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_execution_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_uuid", sa.String(length=64), nullable=False),
        sa.Column("agent_code", sa.String(length=80), nullable=False),
        sa.Column("research_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_scope_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_execution_id"], ["agent_execution.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_uuid", name="uq_research_snapshot_uuid"),
    )
    op.create_index("ix_research_snapshot_generated", "research_snapshot", ["generated_at", "id"])
    op.create_index("ix_research_snapshot_agent_generated", "research_snapshot", ["agent_code", "generated_at", "id"])
    op.create_index("ix_research_snapshot_type_generated", "research_snapshot", ["research_type", "generated_at", "id"])
    op.create_index("ix_research_snapshot_status_generated", "research_snapshot", ["status", "generated_at", "id"])
    op.create_index(op.f("ix_research_snapshot_agent_execution_id"), "research_snapshot", ["agent_execution_id"])
    op.create_index(op.f("ix_research_snapshot_snapshot_uuid"), "research_snapshot", ["snapshot_uuid"])
    op.create_index(op.f("ix_research_snapshot_agent_code"), "research_snapshot", ["agent_code"])
    op.create_index(op.f("ix_research_snapshot_research_type"), "research_snapshot", ["research_type"])
    op.create_index(op.f("ix_research_snapshot_status"), "research_snapshot", ["status"])

    op.create_table(
        "research_finding",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("finding_code", sa.String(length=120), nullable=False),
        sa.Column("finding_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("recommendation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["research_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "finding_code", name="uq_research_finding_snapshot_code"),
    )
    op.create_index("ix_research_finding_snapshot_created", "research_finding", ["snapshot_id", "created_at", "id"])
    op.create_index("ix_research_finding_type_priority", "research_finding", ["finding_type", "priority_score", "id"])
    op.create_index("ix_research_finding_status_priority", "research_finding", ["status", "priority_score", "id"])
    op.create_index(
        "ix_research_finding_confidence_priority",
        "research_finding",
        ["confidence_score", "priority_score", "id"],
    )
    op.create_index(op.f("ix_research_finding_snapshot_id"), "research_finding", ["snapshot_id"])
    op.create_index(op.f("ix_research_finding_finding_type"), "research_finding", ["finding_type"])
    op.create_index(op.f("ix_research_finding_status"), "research_finding", ["status"])

    op.create_table(
        "research_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("finding_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_payload_json", sa.JSON(), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["research_finding.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_evidence_finding_created", "research_evidence", ["finding_id", "created_at", "id"])
    op.create_index("ix_research_evidence_type_score", "research_evidence", ["evidence_type", "evidence_score", "id"])
    op.create_index(op.f("ix_research_evidence_finding_id"), "research_evidence", ["finding_id"])
    op.create_index(op.f("ix_research_evidence_evidence_type"), "research_evidence", ["evidence_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_research_evidence_evidence_type"), table_name="research_evidence")
    op.drop_index(op.f("ix_research_evidence_finding_id"), table_name="research_evidence")
    op.drop_index("ix_research_evidence_type_score", table_name="research_evidence")
    op.drop_index("ix_research_evidence_finding_created", table_name="research_evidence")
    op.drop_table("research_evidence")

    op.drop_index(op.f("ix_research_finding_status"), table_name="research_finding")
    op.drop_index(op.f("ix_research_finding_finding_type"), table_name="research_finding")
    op.drop_index(op.f("ix_research_finding_snapshot_id"), table_name="research_finding")
    op.drop_index("ix_research_finding_confidence_priority", table_name="research_finding")
    op.drop_index("ix_research_finding_status_priority", table_name="research_finding")
    op.drop_index("ix_research_finding_type_priority", table_name="research_finding")
    op.drop_index("ix_research_finding_snapshot_created", table_name="research_finding")
    op.drop_table("research_finding")

    op.drop_index(op.f("ix_research_snapshot_status"), table_name="research_snapshot")
    op.drop_index(op.f("ix_research_snapshot_research_type"), table_name="research_snapshot")
    op.drop_index(op.f("ix_research_snapshot_agent_code"), table_name="research_snapshot")
    op.drop_index(op.f("ix_research_snapshot_snapshot_uuid"), table_name="research_snapshot")
    op.drop_index(op.f("ix_research_snapshot_agent_execution_id"), table_name="research_snapshot")
    op.drop_index("ix_research_snapshot_status_generated", table_name="research_snapshot")
    op.drop_index("ix_research_snapshot_type_generated", table_name="research_snapshot")
    op.drop_index("ix_research_snapshot_agent_generated", table_name="research_snapshot")
    op.drop_index("ix_research_snapshot_generated", table_name="research_snapshot")
    op.drop_table("research_snapshot")
