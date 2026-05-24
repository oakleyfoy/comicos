"""P34-07 Scanner profile presets and scan-session capture linkage.

Revision ID: 20260525_0045
Revises: 20260525_0044
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0045"
down_revision: str | None = "20260525_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scanner_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("profile_name", sa.String(length=200), nullable=False),
        sa.Column("scanner_type", sa.String(length=40), nullable=False),
        sa.Column("dpi", sa.Integer(), nullable=True),
        sa.Column("color_mode", sa.String(length=20), nullable=False),
        sa.Column("file_format", sa.String(length=10), nullable=False),
        sa.Column("duplex_enabled", sa.Boolean(), nullable=False),
        sa.Column("feeder_enabled", sa.Boolean(), nullable=False),
        sa.Column("recommended_use", sa.String(length=40), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scanner_profile_owner_user_id"), "scanner_profile", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_scanner_profile_scanner_type"), "scanner_profile", ["scanner_type"], unique=False)
    op.create_index(
        op.f("ix_scanner_profile_recommended_use"), "scanner_profile", ["recommended_use"], unique=False
    )
    op.create_index(op.f("ix_scanner_profile_is_default"), "scanner_profile", ["is_default"], unique=False)

    op.add_column("scan_session", sa.Column("scanner_profile_id", sa.Integer(), nullable=True))
    op.add_column("scan_session", sa.Column("scanner_profile_snapshot", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_scan_session_scanner_profile_id",
        "scan_session",
        "scanner_profile",
        ["scanner_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_scan_session_scanner_profile_id"),
        "scan_session",
        ["scanner_profile_id"],
        unique=False,
    )

    anchored = datetime.now(timezone.utc)
    seed = [
        {
            "owner_user_id": None,
            "profile_name": "Fujitsu Bulk 300dpi Color PNG",
            "scanner_type": "fujitsu_bulk",
            "dpi": 300,
            "color_mode": "color",
            "file_format": "png",
            "duplex_enabled": True,
            "feeder_enabled": True,
            "recommended_use": "bulk_ingest",
            "is_default": True,
            "notes": "Suggested Fujitsu ADF bulk preset (metadata only — adjust your driver manually).",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "owner_user_id": None,
            "profile_name": "Fujitsu Bulk 400dpi Color PNG",
            "scanner_type": "fujitsu_bulk",
            "dpi": 400,
            "color_mode": "color",
            "file_format": "png",
            "duplex_enabled": True,
            "feeder_enabled": True,
            "recommended_use": "bulk_ingest",
            "is_default": False,
            "notes": "Higher-resolution Fujitsu bulk suggestion.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "owner_user_id": None,
            "profile_name": "Epson High-Res 600dpi Color PNG",
            "scanner_type": "epson_high_res",
            "dpi": 600,
            "color_mode": "color",
            "file_format": "png",
            "duplex_enabled": False,
            "feeder_enabled": False,
            "recommended_use": "high_res_review",
            "is_default": False,
            "notes": "Suggested flatbed/transparency workflow for OCR review scans.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "owner_user_id": None,
            "profile_name": "Epson Archival 1200dpi TIFF",
            "scanner_type": "epson_high_res",
            "dpi": 1200,
            "color_mode": "color",
            "file_format": "tif",
            "duplex_enabled": False,
            "feeder_enabled": False,
            "recommended_use": "archival_scan",
            "is_default": False,
            "notes": "Archival master capture suggestion (large files expected).",
            "created_at": anchored,
            "updated_at": anchored,
        },
    ]
    op.bulk_insert(
        sa.table(
            "scanner_profile",
            sa.column("owner_user_id", sa.Integer()),
            sa.column("profile_name", sa.String(length=200)),
            sa.column("scanner_type", sa.String(length=40)),
            sa.column("dpi", sa.Integer()),
            sa.column("color_mode", sa.String(length=20)),
            sa.column("file_format", sa.String(length=10)),
            sa.column("duplex_enabled", sa.Boolean()),
            sa.column("feeder_enabled", sa.Boolean()),
            sa.column("recommended_use", sa.String(length=40)),
            sa.column("is_default", sa.Boolean()),
            sa.column("notes", sa.Text()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        seed,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scan_session_scanner_profile_id"), table_name="scan_session")
    op.drop_constraint("fk_scan_session_scanner_profile_id", "scan_session", type_="foreignkey")
    op.drop_column("scan_session", "scanner_profile_snapshot")
    op.drop_column("scan_session", "scanner_profile_id")

    op.drop_index(op.f("ix_scanner_profile_is_default"), table_name="scanner_profile")
    op.drop_index(op.f("ix_scanner_profile_recommended_use"), table_name="scanner_profile")
    op.drop_index(op.f("ix_scanner_profile_scanner_type"), table_name="scanner_profile")
    op.drop_index(op.f("ix_scanner_profile_owner_user_id"), table_name="scanner_profile")
    op.drop_table("scanner_profile")
