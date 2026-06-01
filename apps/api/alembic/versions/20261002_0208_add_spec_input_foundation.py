from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261002_0208"
down_revision = "20261001_0207"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spec_input",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=True),
        sa.Column("industry_candidate_id", sa.Integer(), nullable=True),
        sa.Column("future_release_match_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("source_systems", sa.String(length=512), nullable=False),
        sa.Column("signal_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["industry_candidate_id"], ["industry_release_candidate.id"]),
        sa.ForeignKeyConstraint(["future_release_match_id"], ["future_release_match.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spec_input_owner_created", "spec_input", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_spec_input_owner_release", "spec_input", ["owner_user_id", "release_id", "id"])
    op.create_index("ix_spec_input_owner_foc", "spec_input", ["owner_user_id", "foc_date", "id"])
    op.create_index(op.f("ix_spec_input_owner_user_id"), "spec_input", ["owner_user_id"])
    op.create_index(op.f("ix_spec_input_release_id"), "spec_input", ["release_id"])
    op.create_index(op.f("ix_spec_input_industry_candidate_id"), "spec_input", ["industry_candidate_id"])
    op.create_index(op.f("ix_spec_input_future_release_match_id"), "spec_input", ["future_release_match_id"])
    op.create_index(op.f("ix_spec_input_publisher"), "spec_input", ["publisher"])
    op.create_index(op.f("ix_spec_input_foc_date"), "spec_input", ["foc_date"])
    op.create_index(op.f("ix_spec_input_release_date"), "spec_input", ["release_date"])


def downgrade() -> None:
    op.drop_index(op.f("ix_spec_input_release_date"), table_name="spec_input")
    op.drop_index(op.f("ix_spec_input_foc_date"), table_name="spec_input")
    op.drop_index(op.f("ix_spec_input_publisher"), table_name="spec_input")
    op.drop_index(op.f("ix_spec_input_future_release_match_id"), table_name="spec_input")
    op.drop_index(op.f("ix_spec_input_industry_candidate_id"), table_name="spec_input")
    op.drop_index(op.f("ix_spec_input_release_id"), table_name="spec_input")
    op.drop_index(op.f("ix_spec_input_owner_user_id"), table_name="spec_input")
    op.drop_index("ix_spec_input_owner_foc", table_name="spec_input")
    op.drop_index("ix_spec_input_owner_release", table_name="spec_input")
    op.drop_index("ix_spec_input_owner_created", table_name="spec_input")
    op.drop_table("spec_input")
