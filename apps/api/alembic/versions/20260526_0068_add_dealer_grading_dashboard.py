"""P37-08 dealer grading dashboard tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0068"
down_revision: str | None = "20260526_0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dealer_grading_dashboard_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("active_candidate_count", sa.Integer(), nullable=False),
        sa.Column("ready_for_submission_count", sa.Integer(), nullable=False),
        sa.Column("submitted_candidate_count", sa.Integer(), nullable=False),
        sa.Column("graded_candidate_count", sa.Integer(), nullable=False),
        sa.Column("elite_recommendation_count", sa.Integer(), nullable=False),
        sa.Column("high_risk_candidate_count", sa.Integer(), nullable=False),
        sa.Column("low_confidence_candidate_count", sa.Integer(), nullable=False),
        sa.Column("average_estimated_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("average_risk_adjusted_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("active_submission_batch_count", sa.Integer(), nullable=False),
        sa.Column("grading_pipeline_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("estimated_total_submission_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("expected_total_profit", sa.Numeric(18, 2), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_dealer_grading_dashboard_snapshot_owner_replay"),
    )
    op.create_index(
        "ix_dealer_grading_dashboard_snapshot_owner_date",
        "dealer_grading_dashboard_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_grading_dashboard_snapshot_checksum",
        "dealer_grading_dashboard_snapshot",
        ["checksum"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_grading_dashboard_snapshot_replay_key",
        "dealer_grading_dashboard_snapshot",
        ["replay_key"],
        unique=False,
    )

    op.create_table(
        "dealer_grading_dashboard_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=80), nullable=False),
        sa.Column("metric_value_decimal", sa.Numeric(18, 6), nullable=True),
        sa.Column("metric_value_text", sa.Text(), nullable=True),
        sa.Column("metric_metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["dealer_grading_dashboard_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dashboard_snapshot_id", "metric_key", name="uq_dealer_grading_dashboard_metric_snapshot_key"),
    )
    op.create_index(
        "ix_dealer_grading_dashboard_metric_snapshot",
        "dealer_grading_dashboard_metric",
        ["dashboard_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_grading_dashboard_metric_metric_key",
        "dealer_grading_dashboard_metric",
        ["metric_key"],
        unique=False,
    )

    op.create_table(
        "dealer_grading_dashboard_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("alert_replay_key", sa.String(length=200), nullable=False),
        sa.Column("source_candidate_id", sa.Integer(), nullable=True),
        sa.Column("source_submission_batch_id", sa.Integer(), nullable=True),
        sa.Column("source_recommendation_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["dealer_grading_dashboard_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["source_recommendation_id"], ["grading_recommendation.id"]),
        sa.ForeignKeyConstraint(["source_submission_batch_id"], ["grading_submission_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "alert_replay_key", name="uq_dealer_grading_dashboard_alert_owner_replay"),
    )
    op.create_index(
        "ix_dealer_grading_dashboard_alert_owner_created",
        "dealer_grading_dashboard_alert",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_grading_dashboard_alert_owner_dashboard",
        "dealer_grading_dashboard_alert",
        ["owner_user_id", "dashboard_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_grading_dashboard_alert_type_severity",
        "dealer_grading_dashboard_alert",
        ["alert_type", "severity"],
        unique=False,
    )
    op.create_index("ix_dealer_grading_dashboard_alert_source_candidate_id", "dealer_grading_dashboard_alert", ["source_candidate_id"])
    op.create_index(
        "ix_dealer_grading_dashboard_alert_source_submission_batch_id",
        "dealer_grading_dashboard_alert",
        ["source_submission_batch_id"],
    )
    op.create_index(
        "ix_dealer_grading_dashboard_alert_source_recommendation_id",
        "dealer_grading_dashboard_alert",
        ["source_recommendation_id"],
    )

    op.create_table(
        "dealer_grading_dashboard_feed_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("deterministic_key", sa.String(length=200), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["dealer_grading_dashboard_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "deterministic_key", name="uq_dealer_grading_dashboard_feed_owner_key"),
    )
    op.create_index(
        "ix_dealer_grading_dashboard_feed_owner_created",
        "dealer_grading_dashboard_feed_event",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_index("ix_dealer_grading_dashboard_feed_dashboard_snapshot_id", "dealer_grading_dashboard_feed_event", ["dashboard_snapshot_id"])
    op.create_index("ix_dealer_grading_dashboard_feed_event_type", "dealer_grading_dashboard_feed_event", ["event_type"], unique=False)
    op.create_index("ix_dealer_grading_dashboard_feed_source_id", "dealer_grading_dashboard_feed_event", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_dealer_grading_dashboard_feed_source_id", table_name="dealer_grading_dashboard_feed_event")
    op.drop_index("ix_dealer_grading_dashboard_feed_event_type", table_name="dealer_grading_dashboard_feed_event")
    op.drop_index("ix_dealer_grading_dashboard_feed_dashboard_snapshot_id", table_name="dealer_grading_dashboard_feed_event")
    op.drop_index("ix_dealer_grading_dashboard_feed_owner_created", table_name="dealer_grading_dashboard_feed_event")
    op.drop_table("dealer_grading_dashboard_feed_event")

    op.drop_index("ix_dealer_grading_dashboard_alert_source_recommendation_id", table_name="dealer_grading_dashboard_alert")
    op.drop_index("ix_dealer_grading_dashboard_alert_source_submission_batch_id", table_name="dealer_grading_dashboard_alert")
    op.drop_index("ix_dealer_grading_dashboard_alert_source_candidate_id", table_name="dealer_grading_dashboard_alert")
    op.drop_index("ix_dealer_grading_dashboard_alert_type_severity", table_name="dealer_grading_dashboard_alert")
    op.drop_index("ix_dealer_grading_dashboard_alert_owner_dashboard", table_name="dealer_grading_dashboard_alert")
    op.drop_index("ix_dealer_grading_dashboard_alert_owner_created", table_name="dealer_grading_dashboard_alert")
    op.drop_table("dealer_grading_dashboard_alert")

    op.drop_index("ix_dealer_grading_dashboard_metric_metric_key", table_name="dealer_grading_dashboard_metric")
    op.drop_index("ix_dealer_grading_dashboard_metric_snapshot", table_name="dealer_grading_dashboard_metric")
    op.drop_table("dealer_grading_dashboard_metric")

    op.drop_index("ix_dealer_grading_dashboard_snapshot_replay_key", table_name="dealer_grading_dashboard_snapshot")
    op.drop_index("ix_dealer_grading_dashboard_snapshot_checksum", table_name="dealer_grading_dashboard_snapshot")
    op.drop_index("ix_dealer_grading_dashboard_snapshot_owner_date", table_name="dealer_grading_dashboard_snapshot")
    op.drop_table("dealer_grading_dashboard_snapshot")
