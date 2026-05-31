from __future__ import annotations

from app.services.lunar_variant_classifier import classify_lunar_variant


def test_cover_variants_detected() -> None:
    result = classify_lunar_variant(title="ZATANNA (2026) #5 CVR D NIMIT MALAVIA CARD STOCK VAR")
    assert result.cover_code == "D"
    assert result.variant_name.startswith("Cover D")


def test_ratio_incentive_detected() -> None:
    result = classify_lunar_variant(title="BATTLE BEAST #9 CVR B INC 1:25 VIRGIN VAR")
    assert result.ratio_value == 25
    assert result.is_incentive_variant is True


def test_foil_and_special_edition() -> None:
    foil = classify_lunar_variant(title="SAMPLE #1 CVR A FOIL VAR")
    assert "Foil" in foil.variant_name
    signed = classify_lunar_variant(title="SAMPLE #1 SIGNED EDITION")
    assert signed.variant_name == "Signed Edition"
