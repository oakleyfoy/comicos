from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260831_0176"
down_revision = "20260825_0175"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("profile_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_purchase_profile_owner"),
    )
    op.create_index("ix_purchase_profile_owner_active", "purchase_profile", ["owner_user_id", "is_active", "id"])
    op.create_index("ix_purchase_profile_type", "purchase_profile", ["profile_type", "id"])
    op.create_index(op.f("ix_purchase_profile_owner_user_id"), "purchase_profile", ["owner_user_id"])

    op.create_table(
        "purchase_preference",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("preferred_copy_count", sa.Integer(), nullable=False),
        sa.Column("risk_tolerance", sa.Float(), nullable=False),
        sa.Column("variant_interest", sa.Float(), nullable=False),
        sa.Column("grading_interest", sa.Float(), nullable=False),
        sa.Column("completionist_score", sa.Float(), nullable=False),
        sa.Column("speculation_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_purchase_preference_owner"),
    )
    op.create_index(op.f("ix_purchase_preference_owner_user_id"), "purchase_preference", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_preference_owner_user_id"), table_name="purchase_preference")
    op.drop_table("purchase_preference")
    op.drop_index(op.f("ix_purchase_profile_owner_user_id"), table_name="purchase_profile")
    op.drop_index("ix_purchase_profile_type", table_name="purchase_profile")
    op.drop_index("ix_purchase_profile_owner_active", table_name="purchase_profile")
    op.drop_table("purchase_profile")
