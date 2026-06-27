"""P103.5 exception backlog and manual attach tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.intake_queue import ComicIssueBarcode
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters
from app.services.p103_gcd_enrichment_fast import EnrichmentIssueSnapshot, _GcdIndex
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id, gcd_row_to_plan_inputs
from app.services.p1035_gcd_identity_backfill_service import (
    build_comicvine_duplicate_index,
    run_p1035_identity_dryrun,
)
from app.services.p1035_gcd_identity_exception_service import (
    P1035ExceptionCollector,
    explain_ambiguous_gcd_lookup,
    load_exceptions_from_report_file,
    record_ambiguous_match,
    record_duplicate_cv_conflict,
    run_p1035_manual_attach,
    write_p1035_exception_backlog,
)
from tests.test_p1035_gcd_identity_backfill import (
    _minimal_enrichment_cache,
    _superman_39_snap,
    _superman_gcd_row,
)


def test_exception_report_writes_all_json_and_csv(tmp_path: Path) -> None:
    collector = P1035ExceptionCollector()
    collector.ambiguous_matches.append(
        {
            "catalog_issue_id": 1,
            "exception_type": "ambiguous_match",
            "gcd_candidates": [{"gcd_issue_id": 10}, {"gcd_issue_id": 11}],
        }
    )
    collector.duplicate_cv_conflicts.append(
        {
            "catalog_issue_id": 2,
            "catalog_issue_ids": [2, 3],
            "exception_type": "duplicate_cv_conflict",
        }
    )
    out_dir = tmp_path / "exceptions"
    summary = write_p1035_exception_backlog(collector.to_dict(), out_dir)
    assert summary["ambiguous_matches"] == 1
    assert summary["duplicate_cv_conflicts"] == 1
    assert summary["total_manual_review"] == 2
    for stem in (
        "ambiguous_matches",
        "duplicate_cv_conflicts",
        "upc_conflicts",
        "validation_failures",
    ):
        assert (out_dir / f"{stem}.json").is_file()
        assert (out_dir / f"{stem}.csv").is_file()


def test_duplicate_cv_row_lists_both_catalog_issue_ids() -> None:
    a = _superman_39_snap(issue_id=1)
    b = _superman_39_snap(issue_id=2)
    dup = build_comicvine_duplicate_index([a, b])
    scope_by_id = {1: a, 2: b}
    collector = P1035ExceptionCollector()
    record_duplicate_cv_conflict(collector, snap=a, dup_index=dup, scope_by_id=scope_by_id)
    row = collector.duplicate_cv_conflicts[0]
    assert set(row["catalog_issue_ids"]) == {1, 2}
    assert len(row["peer_catalog_issues"]) == 2


def test_ambiguous_row_includes_multiple_gcd_candidates() -> None:
    snap = _superman_39_snap()
    row_a = {"gcd_issue_id": 1, "publisher_norm": "dc comics", "year": 2018}
    row_b = {"gcd_issue_id": 2, "publisher_norm": "dc comics", "year": 2018}
    index = _GcdIndex(exact={}, by_series_issue={}, rows_loaded=2)
    index.by_series_issue[("superman", "39")] = [
        ("dc comics", 2018, row_a),
        ("dc comics", 2018, row_b),
    ]
    reason, candidates = explain_ambiguous_gcd_lookup(index, snap)
    assert reason == "ambiguous_year_tie"
    assert len(candidates) >= 2
    collector = P1035ExceptionCollector()
    record_ambiguous_match(collector, snap=snap, index=index)
    assert len(collector.ambiguous_matches[0]["gcd_candidates"]) >= 2


def test_load_exceptions_from_write_report_file(tmp_path: Path) -> None:
    path = tmp_path / "write.json"
    path.write_text(
        json.dumps(
            {
                "report": {"mode": "identity_backfill_write"},
                "rollback": {},
                "exceptions": {"ambiguous_matches": [{"catalog_issue_id": 5}], "duplicate_cv_conflicts": []},
            }
        ),
        encoding="utf-8",
    )
    data = load_exceptions_from_report_file(path)
    assert len(data["ambiguous_matches"]) == 1


def test_dryrun_populates_exception_collector(session: Session, tmp_path: Path, monkeypatch) -> None:
    a = _superman_39_snap(issue_id=201)
    b = _superman_39_snap(issue_id=202)
    cache_path = tmp_path / "cache.sqlite"
    _minimal_enrichment_cache(cache_path, a)
    conn = __import__("sqlite3").connect(cache_path)
    conn.execute(
        """
        INSERT INTO catalog_enrichment_issue VALUES
        (202, 2018, 1, 10, ?, ?, ?, ?, ?, ?,
         NULL, NULL, NULL, ?, NULL, ?, NULL, NULL, 0)
        """,
        (
            b.publisher_norm,
            b.series_norm,
            b.issue_norm,
            b.publisher_name,
            b.series_name,
            b.issue_number,
            b.title,
            json.dumps(b.external_source_ids),
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
    collector = P1035ExceptionCollector()
    filters = EnrichmentFilters(publisher="DC", year_from=2018, year_to=2018, limit=10)
    report = run_p1035_identity_dryrun(
        gcd_path=tmp_path / "gcd.db",
        cache_path=cache_path,
        filters=filters,
        exception_collector=collector,
    )
    assert report.exceptions is not None
    assert report.duplicate_cv_conflicts >= 2
    assert len(collector.duplicate_cv_conflicts) >= 2


def test_manual_attach_writes_gcd_id(session: Session, tmp_path: Path, monkeypatch) -> None:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman (2016)", normalized_name="superman 2016", publisher_id=int(pub.id))
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="39",
        normalized_issue_number="39",
        title="Test",
        external_source_ids={"COMICVINE": {"654042": {}}},
    )
    session.add(issue)
    session.commit()

    monkeypatch.setattr(
        "app.services.p1035_gcd_identity_exception_service.fetch_gcd_issue_row",
        lambda _p, _i: _superman_gcd_row(),
    )
    result = run_p1035_manual_attach(
        session,
        catalog_issue_id=int(issue.id),
        gcd_issue_id=1777668,
        gcd_path=tmp_path / "gcd.db",
    )
    assert result["fields_updated"] >= 1
    session.refresh(issue)
    assert extract_gcd_issue_id(issue.external_source_ids) == 1777668


def test_manual_attach_inserts_upc_when_valid(session: Session, tmp_path: Path, monkeypatch) -> None:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman (2016)", normalized_name="superman 2016", publisher_id=int(pub.id))
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="39",
        normalized_issue_number="39",
        title="Test",
        external_source_ids={},
    )
    session.add(issue)
    session.commit()

    monkeypatch.setattr(
        "app.services.p1035_gcd_identity_exception_service.fetch_gcd_issue_row",
        lambda _p, _i: _superman_gcd_row(),
    )
    result = run_p1035_manual_attach(
        session,
        catalog_issue_id=int(issue.id),
        gcd_issue_id=1777668,
        gcd_path=tmp_path / "gcd.db",
    )
    assert result["inserted_upc"] is True
    assert session.exec(select(CatalogUpc).where(CatalogUpc.issue_id == int(issue.id))).first()


def test_manual_attach_refuses_upc_conflict(session: Session, tmp_path: Path, monkeypatch) -> None:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(
        name="Superman (2016)",
        normalized_name="superman 2016",
        publisher_id=int(pub.id),
    )
    session.add(series)
    session.commit()
    issue_a = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="39",
        normalized_issue_number="39",
        title="A",
        external_source_ids={},
    )
    issue_b = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="40",
        normalized_issue_number="40",
        title="B",
        external_source_ids={GCD_SOURCE: {"1777668": {}}},
    )
    session.add(issue_a)
    session.add(issue_b)
    session.commit()
    norm = "76194134192703921"
    session.add(CatalogUpc(normalized_upc=norm, upc=norm, issue_id=int(issue_b.id), source="test"))
    session.commit()

    monkeypatch.setattr(
        "app.services.p1035_gcd_identity_exception_service.fetch_gcd_issue_row",
        lambda _p, _i: _superman_gcd_row(),
    )
    with pytest.raises(ValueError, match="UPC conflict"):
        run_p1035_manual_attach(
            session,
            catalog_issue_id=int(issue_a.id),
            gcd_issue_id=1777668,
            gcd_path=tmp_path / "gcd.db",
        )


def test_manual_attach_refuses_gcd_overwrite(session: Session, tmp_path: Path, monkeypatch) -> None:
    series = CatalogSeries(name="Superman (2016)", normalized_name="superman 2016", publisher_id=1)
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        issue_number="39",
        normalized_issue_number="39",
        title="Test",
        external_source_ids={GCD_SOURCE: {"999999": {}}},
    )
    session.add(issue)
    session.commit()

    monkeypatch.setattr(
        "app.services.p1035_gcd_identity_exception_service.fetch_gcd_issue_row",
        lambda _p, _i: _superman_gcd_row(),
    )
    with pytest.raises(ValueError, match="refusing overwrite"):
        run_p1035_manual_attach(
            session,
            catalog_issue_id=int(issue.id),
            gcd_issue_id=1777668,
            gcd_path=tmp_path / "gcd.db",
        )


def test_manual_attach_allows_same_gcd_id(session: Session, tmp_path: Path, monkeypatch) -> None:
    series = CatalogSeries(name="Superman (2016)", normalized_name="superman 2016", publisher_id=1)
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        issue_number="39",
        normalized_issue_number="39",
        title="Test",
        external_source_ids={GCD_SOURCE: {"1777668": {}}},
    )
    session.add(issue)
    session.commit()

    monkeypatch.setattr(
        "app.services.p1035_gcd_identity_exception_service.fetch_gcd_issue_row",
        lambda _p, _i: _superman_gcd_row(),
    )
    result = run_p1035_manual_attach(
        session,
        catalog_issue_id=int(issue.id),
        gcd_issue_id=1777668,
        gcd_path=tmp_path / "gcd.db",
    )
    assert result["catalog_issue_id"] == int(issue.id)
