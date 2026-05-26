"""P36-02 deterministic listing export registry (CSV files; no marketplace posting).

Revision ID: 20260525_0054
Revises: 20260525_0053
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0054"
down_revision: str | None = "20260525_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listing_export_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template_version", sa.String(length=32), nullable=False),
        sa.Column("column_map_json", sa.JSON(), nullable=False),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint(
            "owner_user_id",
            "channel",
            "name",
            name="uq_listing_export_tpl_owner_channel_name",
        ),
    )
    op.create_index(
        "ix_listing_export_tpl_owner_active",
        "listing_export_template",
        ["owner_user_id", "is_active"],
        unique=False,
    )
    op.create_index(op.f("ix_listing_export_template_channel"), "listing_export_template", ["channel"])
    op.create_index(
        op.f("ix_listing_export_template_owner_user_id"),
        "listing_export_template",
        ["owner_user_id"],
        unique=False,
    )

    op.create_table(
        "listing_export_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("requested_listing_count", sa.Integer(), nullable=False),
        sa.Column("exported_listing_count", sa.Integer(), nullable=False),
        sa.Column("skipped_listing_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["listing_export_template.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_listing_export_run_owner_replay"),
    )
    op.create_index(op.f("ix_listing_export_run_channel"), "listing_export_run", ["channel"])
    op.create_index(
        op.f("ix_listing_export_run_owner_user_id"),
        "listing_export_run",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_listing_export_run_owner_created_at",
        "listing_export_run",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "listing_export_run_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("export_run_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("skip_reason", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("row_checksum", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["export_run_id"], ["listing_export_run.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
    )
    op.create_index(
        "ix_listing_export_item_run_row",
        "listing_export_run_item",
        ["export_run_id", "row_number", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_listing_export_run_item_export_run_id"),
        "listing_export_run_item",
        ["export_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_listing_export_run_item_listing_id"),
        "listing_export_run_item",
        ["listing_id"],
        unique=False,
    )

    op.create_table(
        "listing_export_file",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("export_run_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["export_run_id"], ["listing_export_run.id"]),
    )
    op.create_index(
        "ix_listing_export_file_run",
        "listing_export_file",
        ["export_run_id", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_listing_export_file_export_run_id"),
        "listing_export_file",
        ["export_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_listing_export_file_export_run_id"), table_name="listing_export_file")
    op.drop_index("ix_listing_export_file_run", table_name="listing_export_file")
    op.drop_table("listing_export_file")

    op.drop_index(op.f("ix_listing_export_run_item_listing_id"), table_name="listing_export_run_item")
    op.drop_index(op.f("ix_listing_export_run_item_export_run_id"), table_name="listing_export_run_item")
    op.drop_index("ix_listing_export_item_run_row", table_name="listing_export_run_item")
    op.drop_table("listing_export_run_item")

    op.drop_index("ix_listing_export_run_owner_created_at", table_name="listing_export_run")
    op.drop_index(op.f("ix_listing_export_run_owner_user_id"), table_name="listing_export_run")
    op.drop_index(op.f("ix_listing_export_run_channel"), table_name="listing_export_run")
    op.drop_table("listing_export_run")

    op.drop_index(op.f("ix_listing_export_template_owner_user_id"), table_name="listing_export_template")
    op.drop_index(op.f("ix_listing_export_template_channel"), table_name="listing_export_template")
    op.drop_index("ix_listing_export_tpl_owner_active", table_name="listing_export_template")
    op.drop_table("listing_export_template")
