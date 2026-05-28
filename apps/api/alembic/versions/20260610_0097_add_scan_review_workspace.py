"""add scan review workspace

Revision ID: 20260610_0098
Revises: 20260609_0097
Create Date: 2026-06-10 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260610_0098"
down_revision = "20260609_0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_review_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=True),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=True),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("review_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "review_checksum", name="uq_scan_review_session_owner_checksum"),
    )
    op.create_index("ix_scan_review_session_owner_user_id", "scan_review_session", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_review_session_scan_image_id", "scan_review_session", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_review_session_visual_evidence_run_id", "scan_review_session", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_review_session_grading_assistance_run_id", "scan_review_session", ["grading_assistance_run_id"], unique=False)
    op.create_index("ix_scan_review_session_reconciliation_run_id", "scan_review_session", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_review_session_review_status", "scan_review_session", ["review_status"], unique=False)
    op.create_index("ix_scan_review_session_review_checksum", "scan_review_session", ["review_checksum"], unique=False)
    op.create_index("ix_scan_review_session_snapshot_checksum", "scan_review_session", ["snapshot_checksum"], unique=False)
    op.create_index("ix_scan_review_session_reviewer_user_id", "scan_review_session", ["reviewer_user_id"], unique=False)
    op.create_index("ix_scan_review_session_owner_created", "scan_review_session", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_review_session_owner_status", "scan_review_session", ["owner_user_id", "review_status", "id"], unique=False)
    op.create_index("ix_scan_review_session_scan_image", "scan_review_session", ["scan_image_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_review_decision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=48), nullable=False),
        sa.Column("decision_status", sa.String(length=24), nullable=False),
        sa.Column("decision_value", sa.String(length=255), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("reason_text", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_review_decision_owner_user_id", "scan_review_decision", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_review_decision_review_session_id", "scan_review_decision", ["review_session_id"], unique=False)
    op.create_index("ix_scan_review_decision_decision_type", "scan_review_decision", ["decision_type"], unique=False)
    op.create_index("ix_scan_review_decision_decision_status", "scan_review_decision", ["decision_status"], unique=False)
    op.create_index("ix_scan_review_decision_confidence_score", "scan_review_decision", ["confidence_score"], unique=False)
    op.create_index("ix_scan_review_decision_owner_created", "scan_review_decision", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_review_decision_session_type", "scan_review_decision", ["review_session_id", "decision_type", "id"], unique=False)

    op.create_table(
        "scan_review_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("note_type", sa.String(length=32), nullable=False),
        sa.Column("note_text", sa.String(length=4000), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=True),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_review_note_owner_user_id", "scan_review_note", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_review_note_review_session_id", "scan_review_note", ["review_session_id"], unique=False)
    op.create_index("ix_scan_review_note_note_type", "scan_review_note", ["note_type"], unique=False)
    op.create_index("ix_scan_review_note_source_system", "scan_review_note", ["source_system"], unique=False)
    op.create_index("ix_scan_review_note_source_record_id", "scan_review_note", ["source_record_id"], unique=False)
    op.create_index("ix_scan_review_note_owner_created", "scan_review_note", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_review_note_session_type", "scan_review_note", ["review_session_id", "note_type", "id"], unique=False)

    op.create_table(
        "scan_review_evidence_action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("action_status", sa.String(length=16), nullable=False),
        sa.Column("reason_text", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_review_evidence_action_owner_user_id", "scan_review_evidence_action", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_review_evidence_action_review_session_id", "scan_review_evidence_action", ["review_session_id"], unique=False)
    op.create_index("ix_scan_review_evidence_action_source_system", "scan_review_evidence_action", ["source_system"], unique=False)
    op.create_index("ix_scan_review_evidence_action_source_record_id", "scan_review_evidence_action", ["source_record_id"], unique=False)
    op.create_index("ix_scan_review_evidence_action_action_type", "scan_review_evidence_action", ["action_type"], unique=False)
    op.create_index("ix_scan_review_evidence_action_action_status", "scan_review_evidence_action", ["action_status"], unique=False)
    op.create_index("ix_scan_review_action_owner_created", "scan_review_evidence_action", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_review_action_session_source", "scan_review_evidence_action", ["review_session_id", "source_system", "source_record_id", "id"], unique=False)

    op.create_table(
        "scan_review_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_session_id", "artifact_type", "artifact_checksum", name="uq_scan_review_artifact_session_type_checksum"),
    )
    op.create_index("ix_scan_review_artifact_owner_user_id", "scan_review_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_review_artifact_review_session_id", "scan_review_artifact", ["review_session_id"], unique=False)
    op.create_index("ix_scan_review_artifact_artifact_type", "scan_review_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_review_artifact_storage_backend", "scan_review_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_review_artifact_artifact_checksum", "scan_review_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_review_artifact_owner_created", "scan_review_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_review_artifact_session_type", "scan_review_artifact", ["review_session_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_review_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_review_issue_owner_user_id", "scan_review_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_review_issue_review_session_id", "scan_review_issue", ["review_session_id"], unique=False)
    op.create_index("ix_scan_review_issue_issue_type", "scan_review_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_review_issue_severity", "scan_review_issue", ["severity"], unique=False)
    op.create_index("ix_scan_review_issue_owner_created", "scan_review_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_review_issue_session_type", "scan_review_issue", ["review_session_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_review_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("review_session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_review_history_owner_user_id", "scan_review_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_review_history_review_session_id", "scan_review_history", ["review_session_id"], unique=False)
    op.create_index("ix_scan_review_history_event_type", "scan_review_history", ["event_type"], unique=False)
    op.create_index("ix_scan_review_history_event_checksum", "scan_review_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_review_history_owner_created", "scan_review_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_review_history_session_type", "scan_review_history", ["review_session_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_table("scan_review_history")
    op.drop_table("scan_review_issue")
    op.drop_table("scan_review_artifact")
    op.drop_table("scan_review_evidence_action")
    op.drop_table("scan_review_note")
    op.drop_table("scan_review_decision")
    op.drop_table("scan_review_session")
