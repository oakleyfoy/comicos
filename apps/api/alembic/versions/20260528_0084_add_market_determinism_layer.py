"""add market determinism layer

Revision ID: 20260528_0084
Revises: 20260528_0083
Create Date: 2026-05-28 09:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260528_0084"
down_revision = "20260528_0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_determinism_validation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("validation_checksum", sa.String(length=64), nullable=False),
        sa.Column("pipeline_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_stages_checked", sa.Integer(), nullable=False),
        sa.Column("total_invariants_checked", sa.Integer(), nullable=False),
        sa.Column("total_replays_checked", sa.Integer(), nullable=False),
        sa.Column("invariant_failure_count", sa.Integer(), nullable=False),
        sa.Column("checksum_mismatch_count", sa.Integer(), nullable=False),
        sa.Column("replay_failure_count", sa.Integer(), nullable=False),
        sa.Column("ordering_failure_count", sa.Integer(), nullable=False),
        sa.Column("validation_summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "validation_checksum", name="uq_md_val_run_owner_checksum"),
    )
    op.create_table(
        "market_determinism_invariant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_determinism_validation_run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("layer_name", sa.String(length=32), nullable=False),
        sa.Column("invariant_code", sa.String(length=64), nullable=False),
        sa.Column("invariant_status", sa.String(length=16), nullable=False),
        sa.Column("expected_value_json", sa.JSON(), nullable=True),
        sa.Column("actual_value_json", sa.JSON(), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_determinism_validation_run_id"],
            ["market_determinism_validation_run.id"],
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "market_determinism_checksum_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_determinism_validation_run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(length=32), nullable=False),
        sa.Column("upstream_stage_name", sa.String(length=32), nullable=True),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("upstream_checksum", sa.String(length=64), nullable=True),
        sa.Column("current_checksum", sa.String(length=64), nullable=True),
        sa.Column("pipeline_checksum", sa.String(length=64), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_determinism_validation_run_id"],
            ["market_determinism_validation_run.id"],
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "market_determinism_replay_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_determinism_validation_run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("artifact_key", sa.String(length=128), nullable=False),
        sa.Column("replay_status", sa.String(length=16), nullable=False),
        sa.Column("original_checksum", sa.String(length=64), nullable=True),
        sa.Column("replay_checksum", sa.String(length=64), nullable=True),
        sa.Column("pipeline_checksum", sa.String(length=64), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_determinism_validation_run_id"],
            ["market_determinism_validation_run.id"],
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_md_val_owner_created", "market_determinism_validation_run", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_md_val_owner_status", "market_determinism_validation_run", ["owner_user_id", "validation_status", "id"])
    op.create_index("ix_md_val_pipeline", "market_determinism_validation_run", ["pipeline_checksum", "id"])
    op.create_index("ix_md_val_run_owner", "market_determinism_validation_run", ["owner_user_id"], unique=False)
    op.create_index("ix_md_val_run_status", "market_determinism_validation_run", ["validation_status"], unique=False)
    op.create_index("ix_md_val_run_checksum", "market_determinism_validation_run", ["validation_checksum"], unique=False)
    op.create_index("ix_md_val_run_pipeline", "market_determinism_validation_run", ["pipeline_checksum"], unique=False)
    op.create_index("ix_md_val_run_snap", "market_determinism_validation_run", ["snapshot_date"], unique=False)

    op.create_index("ix_md_inv_run", "market_determinism_invariant", ["market_determinism_validation_run_id", "id"])
    op.create_index("ix_md_inv_owner_status", "market_determinism_invariant", ["owner_user_id", "invariant_status", "id"])
    op.create_index("ix_md_inv_owner_layer", "market_determinism_invariant", ["owner_user_id", "layer_name", "id"])
    op.create_index("ix_md_inv_run_id", "market_determinism_invariant", ["market_determinism_validation_run_id"], unique=False)
    op.create_index("ix_md_inv_owner", "market_determinism_invariant", ["owner_user_id"], unique=False)
    op.create_index("ix_md_inv_layer", "market_determinism_invariant", ["layer_name"], unique=False)
    op.create_index("ix_md_inv_code", "market_determinism_invariant", ["invariant_code"], unique=False)
    op.create_index("ix_md_inv_status", "market_determinism_invariant", ["invariant_status"], unique=False)

    op.create_index("ix_md_chk_run", "market_determinism_checksum_audit", ["market_determinism_validation_run_id", "id"])
    op.create_index("ix_md_chk_owner_status", "market_determinism_checksum_audit", ["owner_user_id", "validation_status", "id"])
    op.create_index("ix_md_chk_stage", "market_determinism_checksum_audit", ["stage_name", "upstream_stage_name", "id"])
    op.create_index("ix_md_chk_pipeline", "market_determinism_checksum_audit", ["pipeline_checksum", "id"])
    op.create_index("ix_md_chk_run_id", "market_determinism_checksum_audit", ["market_determinism_validation_run_id"], unique=False)
    op.create_index("ix_md_chk_owner", "market_determinism_checksum_audit", ["owner_user_id"], unique=False)
    op.create_index("ix_md_chk_status", "market_determinism_checksum_audit", ["validation_status"], unique=False)
    op.create_index("ix_md_chk_up", "market_determinism_checksum_audit", ["upstream_checksum"], unique=False)
    op.create_index("ix_md_chk_cur", "market_determinism_checksum_audit", ["current_checksum"], unique=False)

    op.create_index("ix_md_rep_run", "market_determinism_replay_audit", ["market_determinism_validation_run_id", "id"])
    op.create_index("ix_md_rep_owner_status", "market_determinism_replay_audit", ["owner_user_id", "replay_status", "id"])
    op.create_index("ix_md_rep_artifact", "market_determinism_replay_audit", ["artifact_type", "replay_status", "id"])
    op.create_index("ix_md_rep_pipeline", "market_determinism_replay_audit", ["pipeline_checksum", "id"])
    op.create_index("ix_md_rep_run_id", "market_determinism_replay_audit", ["market_determinism_validation_run_id"], unique=False)
    op.create_index("ix_md_rep_owner", "market_determinism_replay_audit", ["owner_user_id"], unique=False)
    op.create_index("ix_md_rep_art", "market_determinism_replay_audit", ["artifact_type"], unique=False)
    op.create_index("ix_md_rep_status", "market_determinism_replay_audit", ["replay_status"], unique=False)
    op.create_index("ix_md_rep_orig", "market_determinism_replay_audit", ["original_checksum"], unique=False)
    op.create_index("ix_md_rep_new", "market_determinism_replay_audit", ["replay_checksum"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_md_rep_new", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_orig", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_status", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_art", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_owner", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_run_id", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_pipeline", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_artifact", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_owner_status", table_name="market_determinism_replay_audit")
    op.drop_index("ix_md_rep_run", table_name="market_determinism_replay_audit")

    op.drop_index("ix_md_chk_cur", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_up", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_status", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_owner", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_run_id", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_pipeline", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_stage", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_owner_status", table_name="market_determinism_checksum_audit")
    op.drop_index("ix_md_chk_run", table_name="market_determinism_checksum_audit")

    op.drop_index("ix_md_inv_status", table_name="market_determinism_invariant")
    op.drop_index("ix_md_inv_code", table_name="market_determinism_invariant")
    op.drop_index("ix_md_inv_layer", table_name="market_determinism_invariant")
    op.drop_index("ix_md_inv_owner", table_name="market_determinism_invariant")
    op.drop_index("ix_md_inv_run_id", table_name="market_determinism_invariant")
    op.drop_index("ix_md_inv_owner_layer", table_name="market_determinism_invariant")
    op.drop_index("ix_md_inv_owner_status", table_name="market_determinism_invariant")
    op.drop_index("ix_md_inv_run", table_name="market_determinism_invariant")

    op.drop_index("ix_md_val_run_snap", table_name="market_determinism_validation_run")
    op.drop_index("ix_md_val_run_pipeline", table_name="market_determinism_validation_run")
    op.drop_index("ix_md_val_run_checksum", table_name="market_determinism_validation_run")
    op.drop_index("ix_md_val_run_status", table_name="market_determinism_validation_run")
    op.drop_index("ix_md_val_run_owner", table_name="market_determinism_validation_run")
    op.drop_index("ix_md_val_pipeline", table_name="market_determinism_validation_run")
    op.drop_index("ix_md_val_owner_status", table_name="market_determinism_validation_run")
    op.drop_index("ix_md_val_owner_created", table_name="market_determinism_validation_run")

    op.drop_table("market_determinism_replay_audit")
    op.drop_table("market_determinism_checksum_audit")
    op.drop_table("market_determinism_invariant")
    op.drop_table("market_determinism_validation_run")
