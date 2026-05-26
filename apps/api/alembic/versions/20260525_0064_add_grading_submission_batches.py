"""P37-04 grading submission batch registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0064"
down_revision: str | None = "20260525_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grading_submission_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("batch_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("submission_date", sa.Date(), nullable=True),
        sa.Column("shipped_date", sa.Date(), nullable=True),
        sa.Column("grader_received_date", sa.Date(), nullable=True),
        sa.Column("grading_started_date", sa.Date(), nullable=True),
        sa.Column("return_shipped_date", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("estimated_turnaround_days", sa.Integer(), nullable=True),
        sa.Column("actual_turnaround_days", sa.Integer(), nullable=True),
        sa.Column("estimated_total_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_total_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_submission_batch_owner_replay"),
    )
    op.create_index(
        "ix_grading_submission_batch_owner_status",
        "grading_submission_batch",
        ["owner_user_id", "status", "target_grader", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_submission_batch_owner_created",
        "grading_submission_batch",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_submission_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_submission_batch_id", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("declared_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_grade", sa.String(length=32), nullable=True),
        sa.Column("final_grade", sa.String(length=32), nullable=True),
        sa.Column("submission_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_submission_batch_id"], ["grading_submission_batch.id"]),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
    )
    op.create_index(
        "ix_grading_submission_item_batch_created",
        "grading_submission_item",
        ["grading_submission_batch_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_submission_item_candidate",
        "grading_submission_item",
        ["grading_candidate_id", "status", "id"],
        unique=False,
    )

    op.create_table(
        "grading_submission_shipment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_submission_batch_id", sa.Integer(), nullable=False),
        sa.Column("shipment_direction", sa.String(length=16), nullable=False),
        sa.Column("carrier", sa.String(length=80), nullable=True),
        sa.Column("tracking_number", sa.String(length=120), nullable=True),
        sa.Column("shipped_date", sa.Date(), nullable=True),
        sa.Column("delivered_date", sa.Date(), nullable=True),
        sa.Column("insured_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("shipping_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_submission_batch_id"], ["grading_submission_batch.id"]),
    )
    op.create_index(
        "ix_grading_submission_shipment_batch_created",
        "grading_submission_shipment",
        ["grading_submission_batch_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_submission_lifecycle_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_submission_batch_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("prior_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_submission_batch_id"], ["grading_submission_batch.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
    )
    op.create_index(
        "ix_grading_submission_lifecycle_event_batch_created",
        "grading_submission_lifecycle_event",
        ["grading_submission_batch_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_submission_cost_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_submission_batch_id", sa.Integer(), nullable=False),
        sa.Column("estimated_grading_fees", sa.Numeric(12, 2), nullable=False),
        sa.Column("estimated_shipping_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("estimated_insurance_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("actual_grading_fees", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_shipping_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_insurance_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_submission_batch_id"], ["grading_submission_batch.id"]),
    )
    op.create_index(
        "ix_grading_submission_cost_snapshot_batch_created",
        "grading_submission_cost_snapshot",
        ["grading_submission_batch_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grading_submission_cost_snapshot_batch_created", table_name="grading_submission_cost_snapshot")
    op.drop_table("grading_submission_cost_snapshot")
    op.drop_index("ix_grading_submission_lifecycle_event_batch_created", table_name="grading_submission_lifecycle_event")
    op.drop_table("grading_submission_lifecycle_event")
    op.drop_index("ix_grading_submission_shipment_batch_created", table_name="grading_submission_shipment")
    op.drop_table("grading_submission_shipment")
    op.drop_index("ix_grading_submission_item_candidate", table_name="grading_submission_item")
    op.drop_index("ix_grading_submission_item_batch_created", table_name="grading_submission_item")
    op.drop_table("grading_submission_item")
    op.drop_index("ix_grading_submission_batch_owner_created", table_name="grading_submission_batch")
    op.drop_index("ix_grading_submission_batch_owner_status", table_name="grading_submission_batch")
    op.drop_table("grading_submission_batch")
