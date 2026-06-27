"""P103.6 targeted identity exception resolution tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from sqlmodel import Session

from app.services.p1036_gcd_identity_exception_resolution_service import (
    P1036_CV_META,
    _relocate_comicvine_id_from_duplicate_shell,
    pick_duplicate_cv_keeper_and_bad,
    resolve_ambiguous_matches_with_evidence,
    score_duplicate_cv_peer,
    write_p1036_outputs,
)
from app.services.p1036_gcd_identity_exception_resolution_service import (
    P1036ResolutionReport,
)


def test_score_duplicate_cv_peer_prefers_gcd_and_upc() -> None:
    rich = {
        "catalog_issue_id": 100,
        "has_upc": True,
        "existing_barcode": "761941341927",
        "existing_external_source_ids": {"GCD": {"123": {}}, "COMICVINE": {"555": {}}},
    }
    shell = {
        "catalog_issue_id": 9000,
        "has_upc": False,
        "existing_external_source_ids": {"COMICVINE": {"555": {}}},
    }
    assert score_duplicate_cv_peer(rich, shared_cv_id="555") > score_duplicate_cv_peer(shell, shared_cv_id="555")


def test_pick_duplicate_cv_keeper_clear_margin() -> None:
    row = {
        "reason": "ComicVine id 555 shared",
        "peer_catalog_issues": [
            {
                "catalog_issue_id": 10,
                "has_upc": True,
                "existing_barcode": "761941341927",
                "existing_external_source_ids": {"GCD": {"1": {}}, "COMICVINE": {"555": {}}},
            },
            {
                "catalog_issue_id": 99,
                "has_upc": False,
                "existing_external_source_ids": {"COMICVINE": {"555": {}}},
            },
        ],
    }
    keeper, bad, reason, margin = pick_duplicate_cv_keeper_and_bad(row)
    assert keeper == 10
    assert bad == 99
    assert reason == "keeper_clear"
    assert margin >= 8


def test_relocate_cv_id_only_from_duplicate_shell() -> None:
    ext = {"COMICVINE": {"555": {"url": "x"}}, "GCD": {"1": {}}}
    out = _relocate_comicvine_id_from_duplicate_shell(ext, comicvine_id="555", keeper_catalog_issue_id=10)
    assert "555" not in (out.get("COMICVINE") or {})
    meta = out.get(P1036_CV_META) or {}
    assert meta.get("duplicate_of_catalog_issue_id") == 10
    assert meta.get("relocated_comicvine_ids")


def test_ambiguous_without_strong_signal_stays_unresolved(
    session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    csv_path = tmp_path / "ambiguous_matches.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["catalog_issue_id", "gcd_candidates", "comicvine_issue_id", "year"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "catalog_issue_id": "999999",
                "gcd_candidates": json.dumps(
                    [{"gcd_issue_id": 1, "gcd_title": "Foo"}, {"gcd_issue_id": 2, "gcd_title": "Bar"}]
                ),
                "comicvine_issue_id": "",
                "year": "2018",
            }
        )

    report = P1036ResolutionReport(dry_run=True)
    resolve_ambiguous_matches_with_evidence(
        session,
        csv_path=csv_path,
        gcd_path=tmp_path / "missing.gcd",
        cache_path=tmp_path / "missing.cache",
        dry_run=True,
        limit=None,
        report=report,
    )
    assert report.counts.ambiguous_still_ambiguous == 1
    assert report.counts.ambiguous_resolved == 0
    assert len(report.final_exceptions.get("ambiguous_matches") or []) == 1


def test_write_p1036_outputs_creates_report_and_remaining(tmp_path: Path) -> None:
    report = P1036ResolutionReport(dry_run=True)
    report.final_exceptions["ambiguous_matches"] = [{"catalog_issue_id": 1}]
    out = write_p1036_outputs(report, tmp_path / "out")
    assert out.is_file()
    assert (tmp_path / "out" / "remaining" / "ambiguous_matches.csv").is_file()
