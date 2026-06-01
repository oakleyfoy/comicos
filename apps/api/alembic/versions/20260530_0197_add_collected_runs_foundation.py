from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260921_0197"
down_revision = "20260920_0196"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collected_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("latest_owned_issue", sa.String(length=32), nullable=False),
        sa.Column("total_owned_issues", sa.Integer(), nullable=False),
        sa.Column("run_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collected_run_owner_created", "collected_run", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_collected_run_publisher_series", "collected_run", ["publisher", "series_name", "id"])
    op.create_index("ix_collected_run_owner_status", "collected_run", ["owner_user_id", "run_status", "id"])
    op.create_index(op.f("ix_collected_run_owner_user_id"), "collected_run", ["owner_user_id"])
    op.create_index(op.f("ix_collected_run_publisher"), "collected_run", ["publisher"])
    op.create_index(op.f("ix_collected_run_run_status"), "collected_run", ["run_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_collected_run_run_status"), table_name="collected_run")
    op.drop_index(op.f("ix_collected_run_publisher"), table_name="collected_run")
    op.drop_index(op.f("ix_collected_run_owner_user_id"), table_name="collected_run")
    op.drop_index("ix_collected_run_owner_status", table_name="collected_run")
    op.drop_index("ix_collected_run_publisher_series", table_name="collected_run")
    op.drop_index("ix_collected_run_owner_created", table_name="collected_run")
    op.drop_table("collected_run")
