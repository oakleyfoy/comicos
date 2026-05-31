from __future__ import annotations

from app.services.lunar_variant_classifier import classify_lunar_variant
from app.services.lunar_variant_identity import build_issue_release_uuid, build_variant_uuid


def test_issue_release_uuid_stable() -> None:
    first = build_issue_release_uuid(publisher="DC Comics", series_name="ZATANNA (2026)", issue_number="5")
    second = build_issue_release_uuid(publisher="DC Comics", series_name="ZATANNA (2026)", issue_number="5")
    assert first == second


def test_variant_uuid_stable() -> None:
    classification = classify_lunar_variant(title="ZATANNA (2026) #5 CVR A JAMAL CAMPBELL")
    first = build_variant_uuid(source_item_code="0626DC0001", upc="123", classification=classification)
    second = build_variant_uuid(source_item_code="0626DC0001", upc="123", classification=classification)
    assert first == second
