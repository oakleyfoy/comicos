"""P38-06 deterministic acquisition-priority intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0075"
down_revision: str | None = "20260527_0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "acquisition_priority_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("acquisition_category", sa.String(length=32), nullable=False),
        sa.Column("acquisition_priority", sa.String(length=16), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False),
        sa.Column("portfolio_impact_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("diversification_impact", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("liquidity_impact", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("grading_upside_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("duplication_risk", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("concentration_reduction_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("estimated_capital_efficiency", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("recommendation_strength", sa.String(length=16), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("rationale_summary", sa.String(length=600), nullable=False),
        sa.Column("warning_flags_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "canonical_comic_issue_id",
            "acquisition_category",
            "snapshot_date",
            "replay_key",
            name="uq_acquisition_priority_snapshot_replay",
        ),
    )
    op.create_index(
        "ix_acquisition_priority_owner_date",
        "acquisition_priority_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_acquisition_priority_owner_priority",
        "acquisition_priority_snapshot",
        ["owner_user_id", "acquisition_priority", "acquisition_category", "id"],
    )
    op.create_index(
        "ix_acquisition_priority_owner_issue_category",
        "acquisition_priority_snapshot",
        ["owner_user_id", "canonical_comic_issue_id", "acquisition_category", "id"],
    )

    op.create_table(
        "acquisition_priority_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("acquisition_priority_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["acquisition_priority_snapshot_id"], ["acquisition_priority_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_acquisition_priority_evidence_snapshot_type",
        "acquisition_priority_evidence",
        ["acquisition_priority_snapshot_id", "evidence_type", "id"],
    )

    op.create_table(
        "acquisition_priority_scenario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("acquisition_priority_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("scenario_name", sa.String(length=16), nullable=False),
        sa.Column("projected_liquidity_impact", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("projected_diversification_impact", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("projected_portfolio_efficiency", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["acquisition_priority_snapshot_id"], ["acquisition_priority_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "acquisition_priority_snapshot_id",
            "scenario_name",
            name="uq_acquisition_priority_scenario_snapshot_name",
        ),
    )

    op.create_table(
        "acquisition_priority_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("acquisition_category", sa.String(length=32), nullable=False),
        sa.Column("acquisition_priority", sa.String(length=16), nullable=False),
        sa.Column("recommendation_strength", sa.String(length=16), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "canonical_comic_issue_id",
            "acquisition_category",
            "snapshot_date",
            "checksum",
            name="uq_acquisition_priority_history_signature",
        ),
    )
    op.create_index(
        "ix_acquisition_priority_history_owner_date",
        "acquisition_priority_history",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_acquisition_priority_history_owner_issue_category",
        "acquisition_priority_history",
        ["owner_user_id", "canonical_comic_issue_id", "acquisition_category", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_acquisition_priority_history_owner_issue_category", table_name="acquisition_priority_history")
    op.drop_index("ix_acquisition_priority_history_owner_date", table_name="acquisition_priority_history")
    op.drop_table("acquisition_priority_history")
    op.drop_table("acquisition_priority_scenario")
    op.drop_index("ix_acquisition_priority_evidence_snapshot_type", table_name="acquisition_priority_evidence")
    op.drop_table("acquisition_priority_evidence")
    op.drop_index("ix_acquisition_priority_owner_issue_category", table_name="acquisition_priority_snapshot")
    op.drop_index("ix_acquisition_priority_owner_priority", table_name="acquisition_priority_snapshot")
    op.drop_index("ix_acquisition_priority_owner_date", table_name="acquisition_priority_snapshot")
    op.drop_table("acquisition_priority_snapshot")
