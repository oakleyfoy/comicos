"""P39-09 market intelligence feed layer."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0082"
down_revision: str | None = "20260528_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_intelligence_feed_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("event_sequence_id", sa.Integer(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=True),
        sa.Column("normalization_run_id", sa.Integer(), nullable=True),
        sa.Column("scoring_run_id", sa.Integer(), nullable=True),
        sa.Column("signal_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("opportunity_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("coupling_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "event_sequence_id",
            name="uq_market_intelligence_feed_event_owner_sequence",
        ),
    )
    op.create_index(
        "ix_market_intelligence_feed_event_sequence",
        "market_intelligence_feed_event",
        ["event_sequence_id", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_event_owner_created",
        "market_intelligence_feed_event",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_event_type_severity",
        "market_intelligence_feed_event",
        ["event_type", "severity", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_event_checksum",
        "market_intelligence_feed_event",
        ["event_checksum", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_event_snapshot_date",
        "market_intelligence_feed_event",
        ["snapshot_date", "id"],
    )

    op.create_table(
        "market_intelligence_feed_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("latest_event_sequence_id", sa.Integer(), nullable=False),
        sa.Column("latest_event_id", sa.Integer(), nullable=True),
        sa.Column("latest_events_json", sa.JSON(), nullable=False),
        sa.Column("owner_timeline_json", sa.JSON(), nullable=False),
        sa.Column("event_type_counts_json", sa.JSON(), nullable=False),
        sa.Column("severity_counts_json", sa.JSON(), nullable=False),
        sa.Column("activity_heatmap_json", sa.JSON(), nullable=False),
        sa.Column("failure_clustering_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["latest_event_id"], ["market_intelligence_feed_event.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "snapshot_date",
            "snapshot_checksum",
            name="uq_market_intelligence_feed_snapshot_signature",
        ),
    )
    op.create_index(
        "ix_market_intelligence_feed_snapshot_owner_date",
        "market_intelligence_feed_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_snapshot_sequence",
        "market_intelligence_feed_snapshot",
        ["latest_event_sequence_id", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_snapshot_checksum",
        "market_intelligence_feed_snapshot",
        ["snapshot_checksum", "id"],
    )

    op.create_table(
        "market_intelligence_feed_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("market_intelligence_feed_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("latest_event_sequence_id", sa.Integer(), nullable=False),
        sa.Column("latest_events_json", sa.JSON(), nullable=False),
        sa.Column("owner_timeline_json", sa.JSON(), nullable=False),
        sa.Column("event_type_counts_json", sa.JSON(), nullable=False),
        sa.Column("severity_counts_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_intelligence_feed_snapshot_id"], ["market_intelligence_feed_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "snapshot_date",
            "snapshot_checksum",
            name="uq_market_intelligence_feed_history_signature",
        ),
    )
    op.create_index(
        "ix_market_intelligence_feed_history_owner_date",
        "market_intelligence_feed_history",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_history_sequence",
        "market_intelligence_feed_history",
        ["latest_event_sequence_id", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_history_checksum",
        "market_intelligence_feed_history",
        ["snapshot_checksum", "id"],
    )

    op.create_table(
        "market_intelligence_feed_cursor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("cursor_key", sa.String(length=128), nullable=False),
        sa.Column("last_event_sequence_id", sa.Integer(), nullable=False),
        sa.Column("last_event_id", sa.Integer(), nullable=True),
        sa.Column("last_event_checksum", sa.String(length=64), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["last_event_id"], ["market_intelligence_feed_event.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "cursor_key",
            name="uq_market_intelligence_feed_cursor_owner_key",
        ),
    )
    op.create_index(
        "ix_market_intelligence_feed_cursor_owner_seq",
        "market_intelligence_feed_cursor",
        ["owner_user_id", "last_event_sequence_id", "id"],
    )
    op.create_index(
        "ix_market_intelligence_feed_cursor_checksum",
        "market_intelligence_feed_cursor",
        ["last_event_checksum", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_intelligence_feed_cursor_checksum", table_name="market_intelligence_feed_cursor")
    op.drop_index("ix_market_intelligence_feed_cursor_owner_seq", table_name="market_intelligence_feed_cursor")
    op.drop_table("market_intelligence_feed_cursor")

    op.drop_index("ix_market_intelligence_feed_history_checksum", table_name="market_intelligence_feed_history")
    op.drop_index("ix_market_intelligence_feed_history_sequence", table_name="market_intelligence_feed_history")
    op.drop_index("ix_market_intelligence_feed_history_owner_date", table_name="market_intelligence_feed_history")
    op.drop_table("market_intelligence_feed_history")

    op.drop_index("ix_market_intelligence_feed_snapshot_checksum", table_name="market_intelligence_feed_snapshot")
    op.drop_index("ix_market_intelligence_feed_snapshot_sequence", table_name="market_intelligence_feed_snapshot")
    op.drop_index("ix_market_intelligence_feed_snapshot_owner_date", table_name="market_intelligence_feed_snapshot")
    op.drop_table("market_intelligence_feed_snapshot")

    op.drop_index("ix_market_intelligence_feed_event_snapshot_date", table_name="market_intelligence_feed_event")
    op.drop_index("ix_market_intelligence_feed_event_checksum", table_name="market_intelligence_feed_event")
    op.drop_index("ix_market_intelligence_feed_event_type_severity", table_name="market_intelligence_feed_event")
    op.drop_index("ix_market_intelligence_feed_event_owner_created", table_name="market_intelligence_feed_event")
    op.drop_index("ix_market_intelligence_feed_event_sequence", table_name="market_intelligence_feed_event")
    op.drop_table("market_intelligence_feed_event")
