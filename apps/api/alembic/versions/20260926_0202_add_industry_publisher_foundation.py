from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260926_0202"
down_revision = "20260925_0201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industry_publisher",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("publisher_code", sa.String(length=32), nullable=False),
        sa.Column("publisher_name", sa.String(length=120), nullable=False),
        sa.Column("scan_enabled", sa.Boolean(), nullable=False),
        sa.Column("inclusion_status", sa.String(length=16), nullable=False),
        sa.Column("scan_priority", sa.Integer(), nullable=False),
        sa.Column("classification_mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "publisher_code", name="uq_industry_publisher_owner_code"),
    )
    op.create_index(
        "ix_industry_publisher_owner_created",
        "industry_publisher",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_industry_publisher_owner_inclusion",
        "industry_publisher",
        ["owner_user_id", "inclusion_status", "id"],
    )
    op.create_index(op.f("ix_industry_publisher_owner_user_id"), "industry_publisher", ["owner_user_id"])
    op.create_index(op.f("ix_industry_publisher_publisher_code"), "industry_publisher", ["publisher_code"])
    op.create_index(op.f("ix_industry_publisher_inclusion_status"), "industry_publisher", ["inclusion_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_industry_publisher_inclusion_status"), table_name="industry_publisher")
    op.drop_index(op.f("ix_industry_publisher_publisher_code"), table_name="industry_publisher")
    op.drop_index(op.f("ix_industry_publisher_owner_user_id"), table_name="industry_publisher")
    op.drop_index("ix_industry_publisher_owner_inclusion", table_name="industry_publisher")
    op.drop_index("ix_industry_publisher_owner_created", table_name="industry_publisher")
    op.drop_table("industry_publisher")
