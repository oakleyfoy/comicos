"""merge live capture and import heads

Revision ID: 445f6d952d77
Revises: 20260608_0273, 20261012_0222
Create Date: 2026-06-09 12:35:34.087740
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '445f6d952d77'
down_revision = ('20260608_0273', '20261012_0222')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
