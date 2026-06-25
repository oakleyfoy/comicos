"""GCD catalog import dashboard helpers."""

from app.services.gcd_catalog_import_dashboard_service import (
    GcdImportCellStats,
    preview_rows_to_csv,
)


def test_preview_rows_to_csv():
    rows = [
        {"gcd_issue_id": 1, "series": "Test", "issue_number": "1", "barcode": "76194134192703921"},
    ]
    text = preview_rows_to_csv(rows)
    assert "gcd_issue_id" in text
    assert "76194134192703921" in text


def test_cell_stats_estimates():
    cell = GcdImportCellStats(publisher="DC", year=2018, gcd_rows=1000, clean_candidates=50)
    d = cell.to_dict()
    assert d["estimated_scan_seconds"] > 0
    assert d["estimated_write_seconds"] > 0


def test_gcd_remaining_stats_total():
    from app.services.gcd_catalog_import_dashboard_service import GcdRemainingPublisherStats

    s = GcdRemainingPublisherStats(
        publisher="DC",
        year_from=2009,
        year_to=2026,
        remaining_clean_candidates=1048,
        already_in_comicos=8061,
        total_clean_primary=9109,
        gcd_rows_in_scope=0,
        variants=0,
        reprints=0,
        foreign_editions=0,
        conflicts=0,
        low_confidence=0,
        barcodes_available=0,
    )
    assert s.remaining_clean_candidates + s.already_in_comicos == s.total_clean_primary
