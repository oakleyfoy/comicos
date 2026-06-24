"""GCD mysqldump -> SQLite loader: streaming parse of needed tables/columns."""

from __future__ import annotations

import sqlite3
from datetime import date

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.services.gcd_barcode_import_service import gcd_engine_from, run_gcd_backfill
from scripts.gcd_load_sqlite import convert_dump_to_sqlite

FULL = "76194134192703921"

# Note: gcd_issue column order differs from our target order, an explicit-column INSERT is
# used for publishers, a non-target table contains commas/parens/quotes, and a series name
# has an escaped quote. All must be handled.
SYNTHETIC_DUMP = """-- GCD synthetic dump
CREATE TABLE `gcd_publisher` (
  `id` int(11) NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
INSERT INTO `gcd_publisher` (`id`,`name`) VALUES (1,'DC Comics'),(2,'Harvey');
CREATE TABLE `gcd_series` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `year_began` int(11) DEFAULT NULL,
  `publisher_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_pub` (`publisher_id`)
) ENGINE=InnoDB;
INSERT INTO `gcd_series` VALUES (10,'Superman',2011,1),(11,'Don\\'t Look',1999,2);
CREATE TABLE `gcd_other` (
  `id` int(11) NOT NULL,
  `blah` text
) ENGINE=InnoDB;
INSERT INTO `gcd_other` VALUES (1,'ignored, with comma and )paren and ; semicolon');
CREATE TABLE `gcd_issue` (
  `id` int(11) NOT NULL,
  `number` varchar(50) DEFAULT NULL,
  `series_id` int(11) NOT NULL,
  `key_date` varchar(10) DEFAULT NULL,
  `barcode` varchar(80) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
INSERT INTO `gcd_issue` VALUES (100,'39',10,'2015-04-00','76194134192703921'),(101,'1',10,'2015-01-00',NULL),(102,'5',11,'1999-06-00','');
"""


def _local_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_superman_39(session: Session) -> int:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id, start_year=2011)
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number="39",
        normalized_issue_number="39",
        cover_date=date(2015, 4, 1),
    )
    session.add(issue)
    session.commit()
    session.add(CatalogVariant(issue_id=int(issue.id), variant_name="Standard"))
    session.commit()
    return int(issue.id)


def test_convert_extracts_needed_tables(tmp_path):
    dump = tmp_path / "gcd_dump.sql"
    dump.write_text(SYNTHETIC_DUMP, encoding="utf-8")
    out = tmp_path / "gcd.sqlite"

    counts = convert_dump_to_sqlite(dump, out)

    assert counts == {"gcd_publisher": 2, "gcd_series": 2, "gcd_issue": 3}
    conn = sqlite3.connect(str(out))
    try:
        # Positional mapping by column name, not dump order.
        row = conn.execute("SELECT number, barcode, key_date, series_id FROM gcd_issue WHERE id=100").fetchone()
        assert row == ("39", FULL, "2015-04-00", 10)
        assert conn.execute("SELECT name FROM gcd_series WHERE id=11").fetchone()[0] == "Don't Look"
        # Non-target table is not created.
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "gcd_other" not in tables
    finally:
        conn.close()


def test_converted_sqlite_feeds_backfill_dryrun(tmp_path):
    dump = tmp_path / "gcd_dump.sql"
    dump.write_text(SYNTHETIC_DUMP, encoding="utf-8")
    out = tmp_path / "gcd.sqlite"
    convert_dump_to_sqlite(dump, out)

    engine = _local_engine()
    with Session(engine) as session:
        issue_id = _seed_superman_39(session)
        gcd = gcd_engine_from(str(out))

        stats = run_gcd_backfill(session, gcd, write=False)

        # issue 100 has a real barcode; 101 is NULL; 102 is empty.
        assert stats.rows_with_barcode == 1
        assert stats.matched_local_issues == 1
        assert stats.projected_inserts == 1
        assert session.exec(select(CatalogUpc)).first() is None
        assert any(s["local_issue_id"] == issue_id for s in stats.samples)
