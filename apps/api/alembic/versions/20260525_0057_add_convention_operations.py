"""P36-05 convention / show operations foundation.

Revision ID: 20260525_0057
Revises: 20260525_0056
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0057"
down_revision: str | None = "20260525_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "convention_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("venue", sa.String(length=160), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=80), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_convention_event_owner_replay"),
    )
    op.create_index("ix_convention_event_owner_status", "convention_event", ["owner_user_id", "status"], unique=False)
    op.create_index("ix_convention_event_owner_dates", "convention_event", ["owner_user_id", "start_date", "end_date", "id"], unique=False)
    op.create_index(op.f("ix_convention_event_owner_user_id"), "convention_event", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_convention_event_start_date"), "convention_event", ["start_date"], unique=False)
    op.create_index(op.f("ix_convention_event_end_date"), "convention_event", ["end_date"], unique=False)
    op.create_index(op.f("ix_convention_event_event_type"), "convention_event", ["event_type"], unique=False)
    op.create_index(op.f("ix_convention_event_status"), "convention_event", ["status"], unique=False)

    op.create_table(
        "convention_inventory_assignment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("convention_event_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("assignment_type", sa.String(length=24), nullable=False),
        sa.Column("local_price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("local_price_currency", sa.String(length=8), nullable=True),
        sa.Column("display_location", sa.String(length=160), nullable=True),
        sa.Column("priority_rank", sa.Integer(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["convention_event_id"], ["convention_event.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_assignment_replay"),
    )
    op.create_index(
        "ix_convention_assignment_event_item_active",
        "convention_inventory_assignment",
        ["convention_event_id", "inventory_item_id", "removed_at", "created_at", "id"],
        unique=False,
    )
    op.create_index("ix_convention_assignment_event_type", "convention_inventory_assignment", ["convention_event_id", "assignment_type"], unique=False)
    op.create_index(op.f("ix_convention_inventory_assignment_convention_event_id"), "convention_inventory_assignment", ["convention_event_id"], unique=False)
    op.create_index(op.f("ix_convention_inventory_assignment_inventory_item_id"), "convention_inventory_assignment", ["inventory_item_id"], unique=False)
    op.create_index(op.f("ix_convention_inventory_assignment_assignment_type"), "convention_inventory_assignment", ["assignment_type"], unique=False)

    op.create_table(
        "convention_inventory_movement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("convention_event_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("movement_type", sa.String(length=24), nullable=False),
        sa.Column("from_location", sa.String(length=160), nullable=True),
        sa.Column("to_location", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["convention_event_id"], ["convention_event.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_movement_replay"),
    )
    op.create_index("ix_convention_movement_event_item_created", "convention_inventory_movement", ["convention_event_id", "inventory_item_id", "created_at", "id"], unique=False)
    op.create_index(op.f("ix_convention_inventory_movement_convention_event_id"), "convention_inventory_movement", ["convention_event_id"], unique=False)
    op.create_index(op.f("ix_convention_inventory_movement_inventory_item_id"), "convention_inventory_movement", ["inventory_item_id"], unique=False)
    op.create_index(op.f("ix_convention_inventory_movement_movement_type"), "convention_inventory_movement", ["movement_type"], unique=False)
    op.create_index(op.f("ix_convention_inventory_movement_created_by_user_id"), "convention_inventory_movement", ["created_by_user_id"], unique=False)

    op.create_table(
        "convention_price_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("convention_event_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("pricing_source", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["convention_event_id"], ["convention_event.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_price_snapshot_replay"),
    )
    op.create_index("ix_convention_price_event_item_created", "convention_price_snapshot", ["convention_event_id", "inventory_item_id", "created_at", "id"], unique=False)
    op.create_index(op.f("ix_convention_price_snapshot_convention_event_id"), "convention_price_snapshot", ["convention_event_id"], unique=False)
    op.create_index(op.f("ix_convention_price_snapshot_inventory_item_id"), "convention_price_snapshot", ["inventory_item_id"], unique=False)
    op.create_index(op.f("ix_convention_price_snapshot_currency"), "convention_price_snapshot", ["currency"], unique=False)
    op.create_index(op.f("ix_convention_price_snapshot_pricing_source"), "convention_price_snapshot", ["pricing_source"], unique=False)

    op.create_table(
        "convention_sale_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("convention_event_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["convention_event_id"], ["convention_event.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_sale_session_replay"),
    )
    op.create_index("ix_convention_sale_session_event_status", "convention_sale_session", ["convention_event_id", "status"], unique=False)
    op.create_index("ix_convention_sale_session_owner_created", "convention_sale_session", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index(op.f("ix_convention_sale_session_convention_event_id"), "convention_sale_session", ["convention_event_id"], unique=False)
    op.create_index(op.f("ix_convention_sale_session_owner_user_id"), "convention_sale_session", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_convention_sale_session_status"), "convention_sale_session", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_convention_sale_session_status"), table_name="convention_sale_session")
    op.drop_index(op.f("ix_convention_sale_session_owner_user_id"), table_name="convention_sale_session")
    op.drop_index(op.f("ix_convention_sale_session_convention_event_id"), table_name="convention_sale_session")
    op.drop_index("ix_convention_sale_session_owner_created", table_name="convention_sale_session")
    op.drop_index("ix_convention_sale_session_event_status", table_name="convention_sale_session")
    op.drop_table("convention_sale_session")

    op.drop_index(op.f("ix_convention_price_snapshot_pricing_source"), table_name="convention_price_snapshot")
    op.drop_index(op.f("ix_convention_price_snapshot_currency"), table_name="convention_price_snapshot")
    op.drop_index(op.f("ix_convention_price_snapshot_inventory_item_id"), table_name="convention_price_snapshot")
    op.drop_index(op.f("ix_convention_price_snapshot_convention_event_id"), table_name="convention_price_snapshot")
    op.drop_index("ix_convention_price_event_item_created", table_name="convention_price_snapshot")
    op.drop_table("convention_price_snapshot")

    op.drop_index(op.f("ix_convention_inventory_movement_created_by_user_id"), table_name="convention_inventory_movement")
    op.drop_index(op.f("ix_convention_inventory_movement_movement_type"), table_name="convention_inventory_movement")
    op.drop_index(op.f("ix_convention_inventory_movement_inventory_item_id"), table_name="convention_inventory_movement")
    op.drop_index(op.f("ix_convention_inventory_movement_convention_event_id"), table_name="convention_inventory_movement")
    op.drop_index("ix_convention_movement_event_item_created", table_name="convention_inventory_movement")
    op.drop_table("convention_inventory_movement")

    op.drop_index(op.f("ix_convention_inventory_assignment_assignment_type"), table_name="convention_inventory_assignment")
    op.drop_index(op.f("ix_convention_inventory_assignment_inventory_item_id"), table_name="convention_inventory_assignment")
    op.drop_index(op.f("ix_convention_inventory_assignment_convention_event_id"), table_name="convention_inventory_assignment")
    op.drop_index("ix_convention_assignment_event_type", table_name="convention_inventory_assignment")
    op.drop_index("ix_convention_assignment_event_item_active", table_name="convention_inventory_assignment")
    op.drop_table("convention_inventory_assignment")

    op.drop_index(op.f("ix_convention_event_status"), table_name="convention_event")
    op.drop_index(op.f("ix_convention_event_event_type"), table_name="convention_event")
    op.drop_index(op.f("ix_convention_event_end_date"), table_name="convention_event")
    op.drop_index(op.f("ix_convention_event_start_date"), table_name="convention_event")
    op.drop_index(op.f("ix_convention_event_owner_user_id"), table_name="convention_event")
    op.drop_index("ix_convention_event_owner_dates", table_name="convention_event")
    op.drop_index("ix_convention_event_owner_status", table_name="convention_event")
    op.drop_table("convention_event")
