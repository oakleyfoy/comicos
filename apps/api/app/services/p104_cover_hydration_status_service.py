"""Read-only P104 cover hydration DB status (table presence, counts, latest run)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect, text
from sqlmodel import Session, select

from app.models.catalog_cover_assets import (
    COVER_ASSET_STATUS_COMPLETE,
    COVER_ASSET_STATUS_FAILED,
    COVER_ASSET_STATUS_PENDING,
    CatalogCoverHydrationRun,
)
from app.services.p104_cover_hydration_service import asset_status_counts

P104_TABLE_ASSETS = "catalog_cover_assets"
P104_TABLE_RUNS = "catalog_cover_hydration_runs"


def p104_table_exists(session: Session, table_name: str) -> bool:
    bind = session.get_bind()
    return inspect(bind).has_table(table_name)


def _read_alembic_version(session: Session) -> str | None:
    bind = session.get_bind()
    try:
        if not inspect(bind).has_table("alembic_version"):
            return None
        row = bind.execute(text("SELECT version_num FROM alembic_version")).first()
        return str(row[0]) if row else None
    except Exception:
        return None


def collect_p104_cover_hydration_status(session: Session) -> dict[str, Any]:
    assets_ok = p104_table_exists(session, P104_TABLE_ASSETS)
    runs_ok = p104_table_exists(session, P104_TABLE_RUNS)
    missing = [t for t, ok in ((P104_TABLE_ASSETS, assets_ok), (P104_TABLE_RUNS, runs_ok)) if not ok]

    payload: dict[str, Any] = {
        "tables": {
            P104_TABLE_ASSETS: assets_ok,
            P104_TABLE_RUNS: runs_ok,
        },
        "tables_missing": bool(missing),
        "missing_tables": missing,
    }

    if missing:
        payload["warning"] = (
            "P104 tables are missing in this database. "
            "Run: cd apps/api && alembic upgrade head "
            "(creates catalog_cover_assets via 20261012_0223; "
            "repair migration 20261029_0231 if already stamped at head)."
        )
        payload["status_by_asset"] = {}
        payload["totals"] = {
            "pending": 0,
            "complete": 0,
            "failed": 0,
            "other": 0,
            "all_assets": 0,
        }
        payload["latest_hydration_run"] = None
        payload["alembic_version"] = _read_alembic_version(session)
        return payload

    status_by_asset = asset_status_counts(session)
    pending = int(status_by_asset.get(COVER_ASSET_STATUS_PENDING, 0))
    complete = int(status_by_asset.get(COVER_ASSET_STATUS_COMPLETE, 0))
    failed = int(status_by_asset.get(COVER_ASSET_STATUS_FAILED, 0))
    all_assets = sum(status_by_asset.values())
    other = max(0, all_assets - pending - complete - failed)

    latest = session.exec(
        select(CatalogCoverHydrationRun).order_by(CatalogCoverHydrationRun.id.desc()).limit(1)
    ).first()

    payload["status_by_asset"] = status_by_asset
    payload["totals"] = {
        "pending": pending,
        "complete": complete,
        "failed": failed,
        "other": other,
        "all_assets": all_assets,
    }
    payload["latest_hydration_run"] = (
        {
            "id": int(latest.id),
            "mode": latest.mode,
            "status": latest.status,
            "requested": latest.requested,
            "queued": latest.queued,
            "downloaded": latest.downloaded,
            "completed": latest.completed,
            "failed": latest.failed,
            "skipped_no_url": latest.skipped_no_url,
            "started_at": latest.started_at.isoformat() if latest.started_at else None,
            "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
        }
        if latest is not None
        else None
    )
    payload["alembic_version"] = _read_alembic_version(session)
    return payload
