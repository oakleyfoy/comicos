"""Index comicvine_volume_universe.name for catalog universe search."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260619_0206"
down_revision: str | None = "20260619_0205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_comicvine_volume_universe_name",
        "comicvine_volume_universe",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_comicvine_volume_universe_name", table_name="comicvine_volume_universe")
