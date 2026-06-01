from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260922_0198"
down_revision = "20260921_0197"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "next_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("current_issue", sa.String(length=32), nullable=False),
        sa.Column("next_issue", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_next_issue_owner_created", "next_issue", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_next_issue_owner_series", "next_issue", ["owner_user_id", "series_name", "id"])
    op.create_index(op.f("ix_next_issue_owner_user_id"), "next_issue", ["owner_user_id"])
    op.create_index(op.f("ix_next_issue_series_name"), "next_issue", ["series_name"])


def downgrade() -> None:
    op.drop_index(op.f("ix_next_issue_series_name"), table_name="next_issue")
    op.drop_index(op.f("ix_next_issue_owner_user_id"), table_name="next_issue")
    op.drop_index("ix_next_issue_owner_series", table_name="next_issue")
    op.drop_index("ix_next_issue_owner_created", table_name="next_issue")
    op.drop_table("next_issue")
