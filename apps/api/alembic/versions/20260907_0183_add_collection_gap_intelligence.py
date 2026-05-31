from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260907_0183"
down_revision = "20260906_0182"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_gap",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("gap_type", sa.String(length=32), nullable=False),
        sa.Column("completion_percent", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collection_gap_owner_created", "collection_gap", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_collection_gap_owner_status", "collection_gap", ["owner_user_id", "gap_type", "id"])
    op.create_index("ix_collection_gap_owner_priority", "collection_gap", ["owner_user_id", "priority", "id"])
    op.create_index(op.f("ix_collection_gap_owner_user_id"), "collection_gap", ["owner_user_id"])
    op.create_index(op.f("ix_collection_gap_gap_type"), "collection_gap", ["gap_type"])
    op.create_index(op.f("ix_collection_gap_priority"), "collection_gap", ["priority"])


def downgrade() -> None:
    op.drop_index(op.f("ix_collection_gap_priority"), table_name="collection_gap")
    op.drop_index(op.f("ix_collection_gap_gap_type"), table_name="collection_gap")
    op.drop_index(op.f("ix_collection_gap_owner_user_id"), table_name="collection_gap")
    op.drop_index("ix_collection_gap_owner_priority", table_name="collection_gap")
    op.drop_index("ix_collection_gap_owner_status", table_name="collection_gap")
    op.drop_index("ix_collection_gap_owner_created", table_name="collection_gap")
    op.drop_table("collection_gap")
