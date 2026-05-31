from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260909_0185"
down_revision = "20260908_0184"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_source_type_active", "marketplace_source", ["source_type", "is_active", "id"])
    op.create_index(op.f("ix_marketplace_source_source_type"), "marketplace_source", ["source_type"])

    op.create_table(
        "marketplace_acquisition_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_source_id", sa.Integer(), nullable=True),
        sa.Column("acquisition_opportunity_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=True),
        sa.Column("series_name", sa.String(length=200), nullable=True),
        sa.Column("issue_number", sa.String(length=32), nullable=True),
        sa.Column("variant_description", sa.String(length=200), nullable=True),
        sa.Column("listing_url", sa.String(length=1024), nullable=True),
        sa.Column("asking_price", sa.Float(), nullable=True),
        sa.Column("shipping_price", sa.Float(), nullable=True),
        sa.Column("total_price", sa.Float(), nullable=True),
        sa.Column("condition_description", sa.String(length=200), nullable=True),
        sa.Column("grade_label", sa.String(length=64), nullable=True),
        sa.Column("seller_name", sa.String(length=200), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column("value_score", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["acquisition_opportunity_id"], ["acquisition_opportunity.id"]),
        sa.ForeignKeyConstraint(["marketplace_source_id"], ["marketplace_source.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mac_owner_status", "marketplace_acquisition_candidate", ["owner_user_id", "status", "id"])
    op.create_index("ix_mac_owner_rec", "marketplace_acquisition_candidate", ["owner_user_id", "recommendation", "id"])
    op.create_index("ix_mac_owner_source", "marketplace_acquisition_candidate", ["owner_user_id", "marketplace_source_id", "id"])
    op.create_index(op.f("ix_marketplace_acquisition_candidate_owner_user_id"), "marketplace_acquisition_candidate", ["owner_user_id"])
    op.create_index(
        op.f("ix_marketplace_acquisition_candidate_marketplace_source_id"),
        "marketplace_acquisition_candidate",
        ["marketplace_source_id"],
    )
    op.create_index(
        op.f("ix_marketplace_acquisition_candidate_acquisition_opportunity_id"),
        "marketplace_acquisition_candidate",
        ["acquisition_opportunity_id"],
    )
    op.create_index(op.f("ix_marketplace_acquisition_candidate_recommendation"), "marketplace_acquisition_candidate", ["recommendation"])
    op.create_index(op.f("ix_marketplace_acquisition_candidate_status"), "marketplace_acquisition_candidate", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_acquisition_candidate_status"), table_name="marketplace_acquisition_candidate")
    op.drop_index(op.f("ix_marketplace_acquisition_candidate_recommendation"), table_name="marketplace_acquisition_candidate")
    op.drop_index(
        op.f("ix_marketplace_acquisition_candidate_acquisition_opportunity_id"),
        table_name="marketplace_acquisition_candidate",
    )
    op.drop_index(
        op.f("ix_marketplace_acquisition_candidate_marketplace_source_id"),
        table_name="marketplace_acquisition_candidate",
    )
    op.drop_index(op.f("ix_marketplace_acquisition_candidate_owner_user_id"), table_name="marketplace_acquisition_candidate")
    op.drop_index("ix_mac_owner_source", table_name="marketplace_acquisition_candidate")
    op.drop_index("ix_mac_owner_rec", table_name="marketplace_acquisition_candidate")
    op.drop_index("ix_mac_owner_status", table_name="marketplace_acquisition_candidate")
    op.drop_table("marketplace_acquisition_candidate")
    op.drop_index(op.f("ix_marketplace_source_source_type"), table_name="marketplace_source")
    op.drop_index("ix_marketplace_source_type_active", table_name="marketplace_source")
    op.drop_table("marketplace_source")
