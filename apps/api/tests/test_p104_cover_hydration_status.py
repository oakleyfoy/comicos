"""P104 table repair migration and hydration status reporting."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine

import app.models  # noqa: F401

from app.models.catalog_cover_assets import (
    COVER_ASSET_STATUS_COMPLETE,
    COVER_ASSET_STATUS_PENDING,
    CatalogCoverAsset,
    CatalogCoverHydrationRun,
    HYDRATION_RUN_STATUS_COMPLETED,
)
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.p104_cover_hydration_status_service import collect_p104_cover_hydration_status


def _engine():
    engine = sqlmodel_create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _load_ensure_p104_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20261029_0231_ensure_p104_cover_tables.py"
    )
    spec = importlib.util.spec_from_file_location("ensure_p104_cover_tables", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ensure_p104_migration_creates_missing_tables() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE catalog_issue (id INTEGER PRIMARY KEY NOT NULL)"))
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('20261028_0230')"))

    mod = _load_ensure_p104_migration()
    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            mod.upgrade()
        connection.commit()

    insp = sa.inspect(engine)
    assert insp.has_table("catalog_cover_assets")
    assert insp.has_table("catalog_cover_hydration_runs")
    cols = {c["name"] for c in insp.get_columns("catalog_cover_assets")}
    assert "last_hydration_run_id" in cols


def test_status_reports_missing_tables_gracefully() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with Session(engine) as session:
        payload = collect_p104_cover_hydration_status(session)
    assert payload["tables_missing"] is True
    assert "catalog_cover_assets" in payload["missing_tables"]
    assert payload.get("warning")


def test_status_reports_counts_when_tables_exist(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    series = CatalogSeries(name="X-Men", normalized_name="x-men", publisher_id=int(pub.id), start_year=2024)
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="1",
        normalized_issue_number="1",
    )
    session.add(issue)
    session.flush()
    session.add(
        CatalogCoverAsset(
            catalog_issue_id=int(issue.id),
            source="COMICVINE",
            source_url="https://example.com/a.jpg",
            status=COVER_ASSET_STATUS_PENDING,
        )
    )
    session.add(
        CatalogCoverAsset(
            catalog_issue_id=int(issue.id),
            source="COMICVINE",
            source_url="https://example.com/b.jpg",
            status=COVER_ASSET_STATUS_COMPLETE,
        )
    )
    run = CatalogCoverHydrationRun(
        mode="batch",
        limit=100,
        status=HYDRATION_RUN_STATUS_COMPLETED,
        requested=2,
        queued=2,
        completed=1,
        failed=0,
    )
    session.add(run)
    session.commit()

    payload = collect_p104_cover_hydration_status(session)
    assert payload["tables_missing"] is False
    assert payload["totals"]["pending"] == 1
    assert payload["totals"]["complete"] == 1
    assert payload["latest_hydration_run"]["id"] == int(run.id)
