"""add p91 collector onboarding state

Revision ID: 20260608_0269
Revises: 20260608_0268
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0269"
down_revision = "20260608_0268"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p77_collector_profile",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "p77_collector_profile",
        sa.Column("onboarding_draft_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    # Existing profiles were created before guided onboarding — do not force the wizard.
    op.execute(
        """
        UPDATE p77_collector_profile
        SET onboarding_completed_at = COALESCE(updated_at, created_at)
        WHERE onboarding_completed_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("p77_collector_profile", "onboarding_draft_json")
    op.drop_column("p77_collector_profile", "onboarding_completed_at")
