"""Add P90 automation and collector alerts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0265"
down_revision = "20260608_0264"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p90_collector_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("action_route", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "alert_type",
            "entity_type",
            "entity_id",
            name="uq_p90_collector_alert_entity",
        ),
    )
    op.create_index(op.f("ix_p90_collector_alert_owner_user_id"), "p90_collector_alert", ["owner_user_id"])
    op.create_index(op.f("ix_p90_collector_alert_alert_type"), "p90_collector_alert", ["alert_type"])
    op.create_index(op.f("ix_p90_collector_alert_severity"), "p90_collector_alert", ["severity"])
    op.create_index(op.f("ix_p90_collector_alert_priority_score"), "p90_collector_alert", ["priority_score"])
    op.create_index(op.f("ix_p90_collector_alert_entity_id"), "p90_collector_alert", ["entity_id"])
    op.create_index(op.f("ix_p90_collector_alert_status"), "p90_collector_alert", ["status"])
    op.create_index("ix_p90_alert_owner_status_pri", "p90_collector_alert", ["owner_user_id", "status", "priority_score"])
    op.create_index("ix_p90_alert_owner_type", "p90_collector_alert", ["owner_user_id", "alert_type", "status"])

    op.create_table(
        "p90_automation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("alerts_created", sa.Integer(), nullable=False),
        sa.Column("alerts_updated", sa.Integer(), nullable=False),
        sa.Column("alerts_dismissed", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_p90_automation_run_owner_user_id"), "p90_automation_run", ["owner_user_id"])
    op.create_index(op.f("ix_p90_automation_run_status"), "p90_automation_run", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_p90_automation_run_status"), table_name="p90_automation_run")
    op.drop_index(op.f("ix_p90_automation_run_owner_user_id"), table_name="p90_automation_run")
    op.drop_table("p90_automation_run")
    op.drop_index("ix_p90_alert_owner_type", table_name="p90_collector_alert")
    op.drop_index("ix_p90_alert_owner_status_pri", table_name="p90_collector_alert")
    op.drop_index(op.f("ix_p90_collector_alert_status"), table_name="p90_collector_alert")
    op.drop_index(op.f("ix_p90_collector_alert_entity_id"), table_name="p90_collector_alert")
    op.drop_index(op.f("ix_p90_collector_alert_priority_score"), table_name="p90_collector_alert")
    op.drop_index(op.f("ix_p90_collector_alert_severity"), table_name="p90_collector_alert")
    op.drop_index(op.f("ix_p90_collector_alert_alert_type"), table_name="p90_collector_alert")
    op.drop_index(op.f("ix_p90_collector_alert_owner_user_id"), table_name="p90_collector_alert")
    op.drop_table("p90_collector_alert")
