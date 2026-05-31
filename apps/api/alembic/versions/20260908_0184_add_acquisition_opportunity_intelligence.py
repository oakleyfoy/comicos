from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260908_0184"
down_revision = "20260907_0183"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acquisition_opportunity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_reference_id", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("variant_description", sa.String(length=200), nullable=True),
        sa.Column("opportunity_type", sa.String(length=32), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("estimated_fmv", sa.Float(), nullable=True),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("value_gap", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_acq_opp_owner_source", "acquisition_opportunity", ["owner_user_id", "source_type", "source_reference_id", "created_at", "id"])
    op.create_index("ix_acq_opp_owner_type", "acquisition_opportunity", ["owner_user_id", "opportunity_type", "id"])
    op.create_index("ix_acq_opp_owner_priority", "acquisition_opportunity", ["owner_user_id", "priority_score", "id"])
    op.create_index(op.f("ix_acquisition_opportunity_owner_user_id"), "acquisition_opportunity", ["owner_user_id"])
    op.create_index(op.f("ix_acquisition_opportunity_source_reference_id"), "acquisition_opportunity", ["source_reference_id"])
    op.create_index(op.f("ix_acquisition_opportunity_opportunity_type"), "acquisition_opportunity", ["opportunity_type"])
    op.create_index(op.f("ix_acquisition_opportunity_priority_score"), "acquisition_opportunity", ["priority_score"])


def downgrade() -> None:
    op.drop_index(op.f("ix_acquisition_opportunity_priority_score"), table_name="acquisition_opportunity")
    op.drop_index(op.f("ix_acquisition_opportunity_opportunity_type"), table_name="acquisition_opportunity")
    op.drop_index(op.f("ix_acquisition_opportunity_source_reference_id"), table_name="acquisition_opportunity")
    op.drop_index(op.f("ix_acquisition_opportunity_owner_user_id"), table_name="acquisition_opportunity")
    op.drop_index("ix_acq_opp_owner_priority", table_name="acquisition_opportunity")
    op.drop_index("ix_acq_opp_owner_type", table_name="acquisition_opportunity")
    op.drop_index("ix_acq_opp_owner_source", table_name="acquisition_opportunity")
    op.drop_table("acquisition_opportunity")
