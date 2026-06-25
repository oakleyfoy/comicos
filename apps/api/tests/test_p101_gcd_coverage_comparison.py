"""P101-B coverage comparison — catalog vs synthetic GCD SQLite."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.p101_gcd_coverage_comparison_service import build_p101_gcd_coverage_report


def _local_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_catalog(session: Session) -> None:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id, start_year=2011)
    session.add(series)
    session.commit()
    session.add(
        CatalogIssue(
            series_id=int(series.id),
            publisher_id=pub.id,
            issue_number="39",
            normalized_issue_number="39",
            cover_date=date(2015, 4, 1),
        )
    )
    session.commit()


def _seed_gcd(path):
    engine = gcd_engine_from(str(path))
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("CREATE TABLE gcd_series (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER)"))
        conn.execute(text("CREATE TABLE gcd_issue (id INTEGER PRIMARY KEY, number TEXT, barcode TEXT, key_date TEXT, series_id INTEGER)"))
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'DC Comics')"))
        conn.execute(text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (1, 'Superman', 2011, 1)"))
        conn.execute(
            text("INSERT INTO gcd_issue (id, number, barcode, key_date, series_id) VALUES (1, '39', 'x', '2015-04-00', 1)")
        )
        conn.execute(
            text("INSERT INTO gcd_issue (id, number, barcode, key_date, series_id) VALUES (2, '40', 'y', '2015-05-00', 1)")
        )
        conn.commit()


def test_gcd_missing_issue_detected(tmp_path):
    catalog_engine = _local_engine()
    gcd_path = tmp_path / "gcd.sqlite"
    _seed_gcd(gcd_path)

    with Session(catalog_engine) as session:
        _seed_catalog(session)
        report = build_p101_gcd_coverage_report(session, gcd=gcd_engine_from(str(gcd_path)), gcd_db=str(gcd_path))

    assert report.totals.comicos_issues == 1
    assert report.totals.gcd_issues == 2
    assert report.totals.missing_from_comicos_in_gcd == 1
    assert report.by_year["2015"].missing_from_comicos_in_gcd == 1
