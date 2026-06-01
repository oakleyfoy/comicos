from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260923_0199"
down_revision = "20260922_0198"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "future_release_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("variant_count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_future_release_match_owner_created",
        "future_release_match",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_future_release_match_owner_series",
        "future_release_match",
        ["owner_user_id", "series_name", "id"],
    )
    op.create_index(op.f("ix_future_release_match_owner_user_id"), "future_release_match", ["owner_user_id"])
    op.create_index(op.f("ix_future_release_match_series_name"), "future_release_match", ["series_name"])
    op.create_index(op.f("ix_future_release_match_foc_date"), "future_release_match", ["foc_date"])
    op.create_index(op.f("ix_future_release_match_release_date"), "future_release_match", ["release_date"])
    op.create_index(op.f("ix_future_release_match_release_id"), "future_release_match", ["release_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_future_release_match_release_id"), table_name="future_release_match")
    op.drop_index(op.f("ix_future_release_match_release_date"), table_name="future_release_match")
    op.drop_index(op.f("ix_future_release_match_foc_date"), table_name="future_release_match")
    op.drop_index(op.f("ix_future_release_match_series_name"), table_name="future_release_match")
    op.drop_index(op.f("ix_future_release_match_owner_user_id"), table_name="future_release_match")
    op.drop_index("ix_future_release_match_owner_series", table_name="future_release_match")
    op.drop_index("ix_future_release_match_owner_created", table_name="future_release_match")
    op.drop_table("future_release_match")
