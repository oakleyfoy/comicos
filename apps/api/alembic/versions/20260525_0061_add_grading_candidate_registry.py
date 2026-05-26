"""P37-01 grading candidate registry."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0061"
down_revision: str | None = "20260525_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grading_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("estimated_raw_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("estimated_graded_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("estimated_spread", sa.Numeric(14, 2), nullable=True),
        sa.Column("estimated_grading_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("estimated_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("candidate_priority", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_candidate_owner_replay"),
    )
    op.create_index(
        "ix_grading_candidate_owner_inventory_status",
        "grading_candidate",
        ["owner_user_id", "inventory_item_id", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_candidate_owner_created",
        "grading_candidate",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_candidate_owner_status",
        "grading_candidate",
        ["owner_user_id", "status", "id"],
        unique=False,
    )

    op.create_table(
        "grading_candidate_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("lineage_domain", sa.String(length=96), nullable=False),
        sa.Column("lineage_key", sa.String(length=256), nullable=False),
        sa.Column("reference_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
    )
    op.create_index(
        "ix_grading_candidate_evidence_candidate_created",
        "grading_candidate_evidence",
        ["grading_candidate_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_candidate_lifecycle_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
    )
    op.create_index(
        "ix_grading_candidate_lc_event_candidate_created",
        "grading_candidate_lifecycle_event",
        ["grading_candidate_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_candidate_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=False),
        sa.Column("assumptions_json", sa.JSON(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
    )
    op.create_index(
        "ix_grading_candidate_snapshot_candidate_created",
        "grading_candidate_snapshot",
        ["grading_candidate_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grading_candidate_snapshot_candidate_created", table_name="grading_candidate_snapshot")
    op.drop_table("grading_candidate_snapshot")
    op.drop_index("ix_grading_candidate_lc_event_candidate_created", table_name="grading_candidate_lifecycle_event")
    op.drop_table("grading_candidate_lifecycle_event")
    op.drop_index("ix_grading_candidate_evidence_candidate_created", table_name="grading_candidate_evidence")
    op.drop_table("grading_candidate_evidence")
    op.drop_index("ix_grading_candidate_owner_status", table_name="grading_candidate")
    op.drop_index("ix_grading_candidate_owner_created", table_name="grading_candidate")
    op.drop_index("ix_grading_candidate_owner_inventory_status", table_name="grading_candidate")
    op.drop_table("grading_candidate")
