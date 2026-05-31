from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260902_0178"
down_revision = "20260901_0177"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_variant_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("cover_label", sa.String(length=160), nullable=False),
        sa.Column("variant_type", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["release_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_var_rec_owner_release_variant",
        "purchase_variant_recommendation",
        ["owner_user_id", "release_id", "variant_id", "created_at", "id"],
    )
    op.create_index(
        "ix_purchase_var_rec_owner_rec",
        "purchase_variant_recommendation",
        ["owner_user_id", "recommendation", "id"],
    )
    op.create_index(
        "ix_purchase_var_rec_owner_type",
        "purchase_variant_recommendation",
        ["owner_user_id", "variant_type", "id"],
    )
    op.create_index(
        op.f("ix_purchase_variant_recommendation_owner_user_id"),
        "purchase_variant_recommendation",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_purchase_variant_recommendation_release_id"),
        "purchase_variant_recommendation",
        ["release_id"],
    )
    op.create_index(
        op.f("ix_purchase_variant_recommendation_variant_id"),
        "purchase_variant_recommendation",
        ["variant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_purchase_variant_recommendation_variant_id"),
        table_name="purchase_variant_recommendation",
    )
    op.drop_index(
        op.f("ix_purchase_variant_recommendation_release_id"),
        table_name="purchase_variant_recommendation",
    )
    op.drop_index(
        op.f("ix_purchase_variant_recommendation_owner_user_id"),
        table_name="purchase_variant_recommendation",
    )
    op.drop_index("ix_purchase_var_rec_owner_type", table_name="purchase_variant_recommendation")
    op.drop_index("ix_purchase_var_rec_owner_rec", table_name="purchase_variant_recommendation")
    op.drop_index("ix_purchase_var_rec_owner_release_variant", table_name="purchase_variant_recommendation")
    op.drop_table("purchase_variant_recommendation")
