"""P37-02 grading spread engine registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0062"
down_revision: str | None = "20260525_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grading_spread_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("raw_fmv_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("graded_fmv_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("grading_cost_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_spread_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_spread_pct", sa.Numeric(18, 8), nullable=True),
        sa.Column("estimated_net_upside", sa.Numeric(12, 2), nullable=True),
        sa.Column("liquidity_adjusted_upside", sa.Numeric(12, 2), nullable=True),
        sa.Column("spread_status", sa.String(length=24), nullable=False),
        sa.Column("liquidity_modifier", sa.String(length=16), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("generation_params_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_spread_snapshot_owner_replay"),
    )
    op.create_index(
        "ix_grading_spread_snapshot_owner_inventory_date",
        "grading_spread_snapshot",
        ["owner_user_id", "inventory_item_id", "snapshot_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_spread_snapshot_owner_status",
        "grading_spread_snapshot",
        ["owner_user_id", "spread_status", "confidence_level", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_spread_snapshot_issue_target",
        "grading_spread_snapshot",
        ["canonical_comic_issue_id", "target_grader", "target_grade", "snapshot_date", "id"],
        unique=False,
    )

    op.create_table(
        "grading_spread_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_spread_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_spread_snapshot_id"], ["grading_spread_snapshot.id"]),
    )
    op.create_index(
        "ix_grading_spread_evidence_snapshot_created",
        "grading_spread_evidence",
        ["grading_spread_snapshot_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_spread_band",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("lower_bound_pct", sa.Numeric(18, 8), nullable=False),
        sa.Column("upper_bound_pct", sa.Numeric(18, 8), nullable=False),
        sa.Column("status_label", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_spread_band_target",
        "grading_spread_band",
        ["target_grader", "target_grade", "status_label", "id"],
        unique=False,
    )

    op.create_table(
        "grading_spread_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("spread_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("spread_pct", sa.Numeric(18, 8), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.UniqueConstraint(
            "owner_user_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "checksum",
            name="uq_grading_spread_history_signature",
        ),
    )
    op.create_index(
        "ix_grading_spread_history_issue_target_date",
        "grading_spread_history",
        ["owner_user_id", "inventory_item_id", "canonical_comic_issue_id", "target_grader", "target_grade", "snapshot_date", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grading_spread_history_issue_target_date", table_name="grading_spread_history")
    op.drop_table("grading_spread_history")
    op.drop_index("ix_grading_spread_band_target", table_name="grading_spread_band")
    op.drop_table("grading_spread_band")
    op.drop_index("ix_grading_spread_evidence_snapshot_created", table_name="grading_spread_evidence")
    op.drop_table("grading_spread_evidence")
    op.drop_index("ix_grading_spread_snapshot_issue_target", table_name="grading_spread_snapshot")
    op.drop_index("ix_grading_spread_snapshot_owner_status", table_name="grading_spread_snapshot")
    op.drop_index("ix_grading_spread_snapshot_owner_inventory_date", table_name="grading_spread_snapshot")
    op.drop_table("grading_spread_snapshot")
