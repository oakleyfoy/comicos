from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260924_0200"
down_revision = "20260923_0199"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "future_release_action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("action_type", sa.String(length=24), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_future_release_action_owner_created",
        "future_release_action",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_future_release_action_owner_series",
        "future_release_action",
        ["owner_user_id", "series_name", "id"],
    )
    op.create_index(
        "ix_future_release_action_type",
        "future_release_action",
        ["owner_user_id", "action_type", "id"],
    )
    op.create_index(op.f("ix_future_release_action_owner_user_id"), "future_release_action", ["owner_user_id"])
    op.create_index(op.f("ix_future_release_action_series_name"), "future_release_action", ["series_name"])
    op.create_index(op.f("ix_future_release_action_action_type"), "future_release_action", ["action_type"])
    op.create_index(op.f("ix_future_release_action_foc_date"), "future_release_action", ["foc_date"])
    op.create_index(op.f("ix_future_release_action_release_id"), "future_release_action", ["release_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_future_release_action_release_id"), table_name="future_release_action")
    op.drop_index(op.f("ix_future_release_action_foc_date"), table_name="future_release_action")
    op.drop_index(op.f("ix_future_release_action_action_type"), table_name="future_release_action")
    op.drop_index(op.f("ix_future_release_action_series_name"), table_name="future_release_action")
    op.drop_index(op.f("ix_future_release_action_owner_user_id"), table_name="future_release_action")
    op.drop_index("ix_future_release_action_type", table_name="future_release_action")
    op.drop_index("ix_future_release_action_owner_series", table_name="future_release_action")
    op.drop_index("ix_future_release_action_owner_created", table_name="future_release_action")
    op.drop_table("future_release_action")
