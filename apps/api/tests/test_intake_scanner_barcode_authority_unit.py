"""Unit tests for intake_scanner_barcode_authority_service (no worker)."""

from __future__ import annotations

from app.services.intake_scanner_barcode_authority_service import (
    DECODE_DISAGREEMENT_REASON,
    barcode_decode_review_reason,
)
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult


def test_supplement_disagreement_requires_rescan() -> None:
    p105 = ComicBarcodeReadResult(supplement_disagreement=True)
    assert barcode_decode_review_reason(p105=p105, normalized="76194134192701911", gcd_path=None) == DECODE_DISAGREEMENT_REASON
