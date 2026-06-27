"""P103.5 GCD identity + UPC backfill tests."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogSeries
from app.models.catalog_p97 import CatalogImportJob, utc_now
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.p101_catalog_cache_service import CatalogCacheContext, CatalogCacheMatcher
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters
from app.services.p103_gcd_enrichment_fast import EnrichmentIssueSnapshot, _GcdIndex
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id, gcd_row_to_plan_inputs
from app.services.p1035_gcd_identity_backfill_service import (
    analyze_p1035_candidate_scope,
    build_comicvine_duplicate_index,
    catalog_issue_ids_from_p1035_resume_metadata,
    load_resume_catalog_issue_ids,
    load_resume_catalog_issue_ids_from_report_file,
    lookup_gcd_for_catalog,
    plan_identity_backfill,
    resolve_p1035_resume_skip_issue_ids,
    run_p1035_identity_write,
)
from app.services.p103_gcd_enrichment_fast import load_catalog_enrichment_scope
from app.services.p1035_gcd_identity_rollback_service import rollback_p1035_identity_job


def _superman_39_snap(*, issue_id: int = 99779, has_upc: bool = False) -> EnrichmentIssueSnapshot:
    return EnrichmentIssueSnapshot(
        issue_id=issue_id,
        year=2018,
        publisher_id=1,
        series_id=2,
        publisher_norm="dc comics",
        series_norm="superman 2016",
        issue_norm="39",
        publisher_name="DC Comics",
        series_name="Superman (2016)",
        issue_number="39",
        cover_date=date(2018, 3, 1),
        release_date=None,
        store_date=None,
        title="The Origin of Superman",
        description=None,
        external_source_ids={"COMICVINE": {"654042": {}}},
        variant_printing=None,
        variant_variant_name=None,
        has_upc=has_upc,
    )


def _superman_gcd_row() -> dict:
    return {
        "issue_id": 1777668,
        "gcd_series_id": 100000,
        "gcd_publisher_id": 4,
        "publisher_name": "DC Comics",
        "series_name": "Superman",
        "number": "39",
        "barcode": "76194134192703921",
        "key_date": "2018-03-00",
        "year_began": 2016,
        "title": "The Origin of Superman",
        "notes": "",
    }


def test_superman_39_series_alias_lookup():
    snap = _superman_39_snap()
    plan_in = gcd_row_to_plan_inputs(_superman_gcd_row())
    index = _GcdIndex(exact={}, by_series_issue={}, rows_loaded=1)
    index.exact[("dc comics", "superman", "39")] = plan_in
    matched = lookup_gcd_for_catalog(index, snap)
    assert matched is not None
    assert int(matched["gcd_issue_id"]) == 1777668


def test_superman_39_plan_links_gcd_and_upc():
    snap = _superman_39_snap()
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes=set(),
    )
    planned, skip, upc_n = plan_identity_backfill(snap, gcd_row_to_plan_inputs(_superman_gcd_row()), ctx=ctx)
    assert skip is None
    assert upc_n == 1
    assert any(p["field"] == "external_source_ids.gcd_issue" for p in planned)
    assert any(p["field"] == "catalog_upc" for p in planned)


def test_duplicate_comicvine_skipped_on_write(session: Session, tmp_path: Path, monkeypatch) -> None:
    a = _superman_39_snap(issue_id=201)
    b = _superman_39_snap(issue_id=202)
    cache_path = tmp_path / "cache.sqlite"
    conn = sqlite3.connect(cache_path)
    conn.executescript(
        """
        CREATE TABLE catalog_issue_cache (issue_id INTEGER PRIMARY KEY, publisher_norm TEXT, series_norm TEXT, issue_norm TEXT, year INTEGER);
        CREATE TABLE catalog_upc_cache (normalized_upc TEXT PRIMARY KEY, issue_id INTEGER NOT NULL);
        CREATE TABLE learned_barcode_cache (normalized_barcode TEXT PRIMARY KEY);
        CREATE TABLE catalog_enrichment_issue (
          issue_id INTEGER PRIMARY KEY, year INTEGER, publisher_id INTEGER, series_id INTEGER,
          publisher_norm TEXT, series_norm TEXT, issue_norm TEXT,
          publisher_name TEXT, series_name TEXT, issue_number TEXT,
          cover_date TEXT, release_date TEXT, store_date TEXT, title TEXT, description TEXT,
          external_source_ids TEXT, variant_printing TEXT, variant_variant_name TEXT, has_upc INTEGER
        );
        """
    )
    for snap in (a, b):
        conn.execute(
            """
            INSERT INTO catalog_enrichment_issue VALUES
            (?, ?, 1, 10, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, ?, NULL, NULL, 0)
            """,
            (
                snap.issue_id,
                snap.year,
                snap.publisher_norm,
                snap.series_norm,
                snap.issue_norm,
                snap.publisher_name,
                snap.series_name,
                snap.issue_number,
                snap.title,
                json.dumps(snap.external_source_ids),
            ),
        )
    conn.commit()
    conn.close()

    plan_in = gcd_row_to_plan_inputs(_superman_gcd_row())

    def _fake_index(*_a, **_k):
        idx = _GcdIndex(exact={}, by_series_issue={}, rows_loaded=1)
        idx.exact[("dc comics", "superman", "39")] = plan_in
        return idx

    monkeypatch.setattr(
        "app.services.p1035_gcd_identity_backfill_service.load_gcd_index_for_enrichment",
        _fake_index,
    )
    filters = EnrichmentFilters(publisher="DC", year_from=2018, year_to=2018, limit=10)
    report = run_p1035_identity_write(
        session,
        gcd_path=tmp_path / "gcd.db",
        cache_path=cache_path,
        filters=filters,
    )
    assert report.duplicate_cv_conflicts >= 2
    assert report.updated_issues == 0


def test_duplicate_comicvine_refuses_plan():
    a = _superman_39_snap(issue_id=1)
    b = _superman_39_snap(issue_id=2)
    dup = build_comicvine_duplicate_index([a, b])
    assert "654042" in dup
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes=set(),
    )
    planned, skip, _ = plan_identity_backfill(a, gcd_row_to_plan_inputs(_superman_gcd_row()), ctx=ctx)
    assert planned  # plan still ok — write loop skips via dup index
    assert len(dup["654042"]) == 2


def test_existing_upc_skips_insert():
    snap = _superman_39_snap(has_upc=True)
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes=set(),
    )
    planned, skip, upc_n = plan_identity_backfill(snap, gcd_row_to_plan_inputs(_superman_gcd_row()), ctx=ctx)
    assert upc_n == 0
    assert not any(p["field"] == "catalog_upc" for p in planned)
    assert any(p["field"] == "external_source_ids.gcd_issue" for p in planned)


def test_learned_barcode_conflict():
    snap = _superman_39_snap()
    norm = "76194134192703921"
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes={norm},
    )
    planned, skip, _ = plan_identity_backfill(snap, gcd_row_to_plan_inputs(_superman_gcd_row()), ctx=ctx)
    assert skip == "learned_barcode_conflict"
    assert planned == []


def test_gcd_tie_refuses_lookup():
    snap = _superman_39_snap()
    row_a = {"gcd_issue_id": 1, "publisher_norm": "dc comics", "year": 2018}
    row_b = {"gcd_issue_id": 2, "publisher_norm": "dc comics", "year": 2018}
    index = _GcdIndex(exact={}, by_series_issue={}, rows_loaded=2)
    index.by_series_issue[("superman", "39")] = [
        ("dc comics", 2018, row_a),
        ("dc comics", 2018, row_b),
    ]
    assert lookup_gcd_for_catalog(index, snap) is None


def _minimal_enrichment_cache(path: Path, snap: EnrichmentIssueSnapshot) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE catalog_issue_cache (issue_id INTEGER PRIMARY KEY, publisher_norm TEXT, series_norm TEXT, issue_norm TEXT, year INTEGER);
        CREATE TABLE catalog_upc_cache (normalized_upc TEXT PRIMARY KEY, issue_id INTEGER NOT NULL);
        CREATE TABLE learned_barcode_cache (normalized_barcode TEXT PRIMARY KEY);
        CREATE TABLE catalog_enrichment_issue (
          issue_id INTEGER PRIMARY KEY, year INTEGER, publisher_id INTEGER, series_id INTEGER,
          publisher_norm TEXT, series_norm TEXT, issue_norm TEXT,
          publisher_name TEXT, series_name TEXT, issue_number TEXT,
          cover_date TEXT, release_date TEXT, store_date TEXT, title TEXT, description TEXT,
          external_source_ids TEXT, variant_printing TEXT, variant_variant_name TEXT, has_upc INTEGER
        );
        """
    )
    conn.execute(
        """
        INSERT INTO catalog_enrichment_issue VALUES
        (?, ?, 1, 10, ?, ?, ?, ?, ?, ?,
         ?, NULL, NULL, ?, NULL, ?, NULL, NULL, ?)
        """,
        (
            snap.issue_id,
            snap.year,
            snap.publisher_norm,
            snap.series_norm,
            snap.issue_norm,
            snap.publisher_name,
            snap.series_name,
            snap.issue_number,
            snap.cover_date.isoformat() if snap.cover_date else None,
            snap.title,
            json.dumps(snap.external_source_ids),
            1 if snap.has_upc else 0,
        ),
    )
    conn.commit()
    conn.close()


def test_write_and_rollback_metadata(session: Session, tmp_path: Path, monkeypatch) -> None:
    snap = _superman_39_snap(issue_id=101)
    series = CatalogSeries(name="Superman (2016)", normalized_name="superman 2016", publisher_id=1)
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        issue_number="39",
        normalized_issue_number="39",
        title="The Origin of Superman",
        external_source_ids={"COMICVINE": {"654042": {}}},
    )
    session.add(issue)
    session.commit()
    snap = _superman_39_snap(issue_id=int(issue.id))

    cache_path = tmp_path / "cache.sqlite"
    _minimal_enrichment_cache(cache_path, snap)

    plan_in = gcd_row_to_plan_inputs(_superman_gcd_row())

    def _fake_index(*_a, **_k):
        idx = _GcdIndex(exact={}, by_series_issue={}, rows_loaded=1)
        idx.exact[("dc comics", "superman", "39")] = plan_in
        return idx

    monkeypatch.setattr(
        "app.services.p1035_gcd_identity_backfill_service.load_gcd_index_for_enrichment",
        _fake_index,
    )

    rollback: dict = {"upc_ids": [], "issue_snapshots": []}
    filters = EnrichmentFilters(publisher="DC", year_from=2018, year_to=2018, limit=10)
    report = run_p1035_identity_write(
        session,
        gcd_path=tmp_path / "gcd.db",
        cache_path=cache_path,
        filters=filters,
        rollback_collector=rollback,
    )
    assert report.updated_issues == 1
    assert report.inserted_upcs == 1
    assert len(rollback["issue_snapshots"]) == 1
    assert rollback["issue_snapshots"][0].get("identity_only") is True
    assert len(rollback["upc_ids"]) == 1

    session.refresh(issue)
    assert extract_gcd_issue_id(issue.external_source_ids) == 1777668

    job = CatalogImportJob(
        source=GCD_SOURCE,
        job_type="gcd_identity_backfill_write",
        status="completed",
        config={"rollback": rollback, "report": report.to_json()},
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(job)
    session.commit()

    result = rollback_p1035_identity_job(session, int(job.id or 0))
    assert int(result["removed_upcs"]) == 1
    session.refresh(issue)
    assert extract_gcd_issue_id(issue.external_source_ids) is None


def _enrichment_cache_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE catalog_issue_cache (issue_id INTEGER PRIMARY KEY, publisher_norm TEXT, series_norm TEXT, issue_norm TEXT, year INTEGER);
        CREATE TABLE catalog_upc_cache (normalized_upc TEXT PRIMARY KEY, issue_id INTEGER NOT NULL);
        CREATE TABLE learned_barcode_cache (normalized_barcode TEXT PRIMARY KEY);
        CREATE TABLE catalog_enrichment_issue (
          issue_id INTEGER PRIMARY KEY, year INTEGER, publisher_id INTEGER, series_id INTEGER,
          publisher_norm TEXT, series_norm TEXT, issue_norm TEXT,
          publisher_name TEXT, series_name TEXT, issue_number TEXT,
          cover_date TEXT, release_date TEXT, store_date TEXT, title TEXT, description TEXT,
          external_source_ids TEXT, variant_printing TEXT, variant_variant_name TEXT, has_upc INTEGER
        );
        """
    )


def _insert_enrichment_row(
    conn: sqlite3.Connection,
    *,
    issue_id: int,
    publisher_name: str = "DC Comics",
    publisher_norm: str = "dc comics",
    series_norm: str = "batman",
    issue_norm: str = "1",
    year: int | None = None,
    cover_date: str | None = None,
    external_source_ids: dict | None = None,
) -> None:
    ext = json.dumps(external_source_ids) if external_source_ids is not None else None
    conn.execute(
        """
        INSERT INTO catalog_enrichment_issue VALUES
        (?, ?, 1, 10, ?, ?, ?, ?, 'Batman', '1',
         ?, NULL, NULL, 'Title', NULL, ?, NULL, NULL, 0)
        """,
        (issue_id, year, publisher_norm, series_norm, issue_norm, publisher_name, cover_date, ext),
    )


def test_extract_gcd_issue_id_shapes():
    assert extract_gcd_issue_id(None) is None
    assert extract_gcd_issue_id({}) is None
    assert extract_gcd_issue_id({"COMICVINE": {"654042": {}}}) is None
    assert extract_gcd_issue_id({"GCD": {"1777668": {}}}) == 1777668
    assert extract_gcd_issue_id({"gcd_issue_id": 1777668}) == 1777668
    assert extract_gcd_issue_id({"gcd": {"issue_id": 1777668}}) == 1777668
    assert extract_gcd_issue_id({"sources": {"gcd": 1777668}}) == 1777668


def test_candidate_scope_includes_null_external(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    conn = sqlite3.connect(cache_path)
    _enrichment_cache_schema(conn)
    _insert_enrichment_row(conn, issue_id=1, year=2018, external_source_ids=None)
    conn.commit()
    conn.close()
    filters = EnrichmentFilters(publisher="DC", year_from=2018, year_to=2018, all_catalog=False, year_filter_explicit=True)
    stats = analyze_p1035_candidate_scope(cache_path, filters)
    assert stats.without_gcd_id == 1
    assert stats.final_candidates == 1


def test_candidate_scope_includes_comicvine_only(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    conn = sqlite3.connect(cache_path)
    _enrichment_cache_schema(conn)
    _insert_enrichment_row(
        conn,
        issue_id=2,
        year=2019,
        external_source_ids={"COMICVINE": {"12345": {}}},
    )
    conn.commit()
    conn.close()
    filters = EnrichmentFilters(publisher="DC", year_from=2019, year_to=2019, all_catalog=False, year_filter_explicit=True)
    stats = analyze_p1035_candidate_scope(cache_path, filters)
    assert stats.final_candidates == 1


def test_candidate_scope_excludes_existing_gcd(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    conn = sqlite3.connect(cache_path)
    _enrichment_cache_schema(conn)
    _insert_enrichment_row(
        conn,
        issue_id=3,
        year=2020,
        external_source_ids={"GCD": {"999": {}}},
    )
    conn.commit()
    conn.close()
    filters = EnrichmentFilters(publisher="DC", year_from=2020, year_to=2020, all_catalog=False, year_filter_explicit=True)
    stats = analyze_p1035_candidate_scope(cache_path, filters)
    assert stats.without_gcd_id == 0
    assert stats.final_candidates == 0


def test_all_bypasses_publisher_filter(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    conn = sqlite3.connect(cache_path)
    _enrichment_cache_schema(conn)
    _insert_enrichment_row(conn, issue_id=4, year=2018, publisher_name="Marvel Comics", publisher_norm="marvel comics")
    _insert_enrichment_row(conn, issue_id=5, year=2018, publisher_name="DC Comics", publisher_norm="dc comics")
    conn.commit()
    conn.close()
    filters = EnrichmentFilters(
        publisher=None,
        year_from=2018,
        year_to=2018,
        all_catalog=True,
        year_filter_explicit=True,
    )
    stats = analyze_p1035_candidate_scope(cache_path, filters)
    assert stats.after_publisher_filter == 2
    assert stats.final_candidates == 2


def test_year_filter_from_cover_date_when_year_null(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    conn = sqlite3.connect(cache_path)
    _enrichment_cache_schema(conn)
    _insert_enrichment_row(conn, issue_id=6, year=None, cover_date="2015-06-01", external_source_ids={})
    _insert_enrichment_row(conn, issue_id=7, year=None, cover_date="1999-01-01", external_source_ids={})
    conn.commit()
    conn.close()
    filters = EnrichmentFilters(
        publisher=None,
        year_from=2010,
        year_to=2020,
        all_catalog=True,
        year_filter_explicit=True,
    )
    scope = load_catalog_enrichment_scope(cache_path, filters=filters)
    assert {s.issue_id for s in scope} == {6}
    stats = analyze_p1035_candidate_scope(cache_path, filters)
    assert stats.after_year_filter == 1


def test_publisher_dc_matches_dc_comics(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite"
    conn = sqlite3.connect(cache_path)
    _enrichment_cache_schema(conn)
    _insert_enrichment_row(
        conn,
        issue_id=8,
        year=2018,
        publisher_name="DC Comics, Inc.",
        publisher_norm="dc comics inc",
    )
    conn.commit()
    conn.close()
    filters = EnrichmentFilters(publisher="DC", year_from=2018, year_to=2018, all_catalog=False, year_filter_explicit=True)
    stats = analyze_p1035_candidate_scope(cache_path, filters)
    assert stats.after_publisher_filter == 1


def test_resume_skip_ids_from_integer_job_id(session: Session) -> None:
    job = CatalogImportJob(
        source=GCD_SOURCE,
        job_type="gcd_identity_backfill_write",
        status="completed",
        config={
            "report": {"written_rows": [{"catalog_issue_id": 10}, {"catalog_issue_id": 11}]},
            "rollback": {"issue_snapshots": [{"catalog_issue_id": 12}]},
        },
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(job)
    session.commit()
    assert job.id is not None
    ids = resolve_p1035_resume_skip_issue_ids(session, int(job.id))
    assert ids == {10, 11, 12}
    assert load_resume_catalog_issue_ids(session, int(job.id)) == ids


def test_resume_skip_ids_from_json_report_path(session: Session, tmp_path: Path) -> None:
    report_path = tmp_path / "prior_write.json"
    report_path.write_text(
        json.dumps(
            {
                "report": {"written_rows": [{"catalog_issue_id": 501}, {"catalog_issue_id": 502}]},
                "rollback": {"issue_snapshots": [{"catalog_issue_id": 503}]},
            }
        ),
        encoding="utf-8",
    )
    ids = load_resume_catalog_issue_ids_from_report_file(report_path)
    assert ids == {501, 502, 503}
    assert resolve_p1035_resume_skip_issue_ids(session, str(report_path)) == ids


def test_resume_skip_ids_json_path_matches_job_metadata(session: Session, tmp_path: Path) -> None:
    rollback = {"issue_snapshots": [{"catalog_issue_id": 99, "identity_only": True}]}
    report = {"written_rows": [{"catalog_issue_id": 88, "gcd_issue_id": 1}]}
    job = CatalogImportJob(
        source=GCD_SOURCE,
        job_type="gcd_identity_backfill_write",
        status="completed",
        config={"report": report, "rollback": rollback},
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(job)
    session.commit()
    path = tmp_path / "write.json"
    path.write_text(json.dumps({"report": report, "rollback": rollback}), encoding="utf-8")
    from_job = resolve_p1035_resume_skip_issue_ids(session, int(job.id or 0))
    from_file = resolve_p1035_resume_skip_issue_ids(session, str(path))
    assert from_job == from_file == {88, 99}


def test_resume_report_file_not_found(session: Session, tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    try:
        load_resume_catalog_issue_ids_from_report_file(missing)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "nope.json" in str(exc)


def test_resume_report_malformed_json(session: Session, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    try:
        load_resume_catalog_issue_ids_from_report_file(bad)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "valid JSON" in str(exc)


def test_catalog_issue_ids_from_resume_metadata_empty_report() -> None:
    assert catalog_issue_ids_from_p1035_resume_metadata(report={}, rollback={}) == set()
