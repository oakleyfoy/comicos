from __future__ import annotations

from app.services.lunar_csv_parser import parse_lunar_product_csv, row_product_code
from lunar_feed_test_helpers import SAMPLE_CSV


def test_parse_lunar_product_csv() -> None:
    rows = parse_lunar_product_csv(SAMPLE_CSV)
    assert len(rows) == 1
    assert row_product_code(rows[0]) == "JUN260001"
