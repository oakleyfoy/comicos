from __future__ import annotations

from app.services.lunar_csv_parser import parse_lunar_product_csv
from app.services.lunar_release_normalizer import normalize_lunar_rows
from lunar_feed_test_helpers import SAMPLE_CSV


def test_normalize_lunar_rows_builds_feed() -> None:
    rows = parse_lunar_product_csv(SAMPLE_CSV)
    feed, errors = normalize_lunar_rows(rows)
    assert not errors
    assert feed.series[0].publisher == "Image"
    assert feed.series[0].issues[0].issue_number == "8"
