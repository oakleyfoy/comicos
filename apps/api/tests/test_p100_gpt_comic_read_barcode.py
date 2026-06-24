"""P100-28 barcode extraction + GPT Comic Read enrichment."""

from __future__ import annotations

import io
from unittest import mock

from PIL import Image
from sqlmodel import Session

from app.services.gpt_comic_read_service import GptComicReadResult
from app.services.p100_barcode_extraction_service import accept_gpt_barcode_digits, extract_barcode_from_image
from app.services.p100_gpt_comic_read_enrichment import resolve_final_match_source, run_gpt_comic_read_enriched


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 300), color=(30, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_gpt() -> GptComicReadResult:
    return GptComicReadResult(
        publisher="DC",
        series="Superman",
        issue_number="39",
        issue_title="",
        year="2024",
        cover_date="",
        variant_description="",
        barcode="",
        confidence=0.88,
        reasoning="Cover reads Superman #39.",
        model="gpt-4o",
        image_width=200,
        image_height=300,
        raw_response={"parsed": {}},
        possible_alternates=[],
    )


def test_no_barcode_visible_returns_null_without_failing_read(session: Session) -> None:
    empty_barcode = {
        "barcode": None,
        "barcode_type": None,
        "confidence": 0.0,
        "method": "none",
        "crop_used": None,
        "error": None,
    }
    with mock.patch("app.services.p100_gpt_comic_read_enrichment.read_comic_with_gpt", return_value=_fake_gpt()):
        with mock.patch(
            "app.services.p100_gpt_comic_read_enrichment.extract_barcode_from_image",
            return_value=empty_barcode,
        ):
            with mock.patch(
                "app.services.p100_gpt_comic_read_enrichment.lookup_comicvine_by_barcode",
            ) as cv_lookup:
                payload = run_gpt_comic_read_enriched(session, _png_bytes(), filename="supes.png")

    assert payload["gpt_read"]["series"] == "Superman"
    assert payload["gpt_read"]["issue_number"] == "39"
    assert payload["barcode_read"]["barcode"] is None
    assert payload["final_match_source"] == "gpt_only"
    cv_lookup.assert_not_called()


def test_fake_local_barcode_gets_normalized() -> None:
    raw = "761941343730"  # valid check digit
    with mock.patch(
        "app.services.p100_barcode_extraction_service._local_decode",
        return_value={
            "barcode": raw,
            "barcode_type": "upc_a",
            "confidence": 0.95,
            "method": "local_decode",
            "crop_used": "bottom_left",
            "error": None,
        },
    ):
        result = extract_barcode_from_image(_png_bytes(), allow_gpt_fallback=False)
    assert result["barcode"] == raw
    assert result["method"] == "local_decode"


def test_invalid_gpt_barcode_text_is_rejected() -> None:
    assert accept_gpt_barcode_digits("75960604387") is None  # too short / bad check
    assert accept_gpt_barcode_digits("not digits") is None
    assert accept_gpt_barcode_digits("761941343730") == "761941343730"


def test_barcode_match_outranks_gpt_catalog_match(session: Session) -> None:
    barcode = "761941343730"
    with mock.patch("app.services.p100_gpt_comic_read_enrichment.read_comic_with_gpt", return_value=_fake_gpt()):
        with mock.patch(
            "app.services.p100_gpt_comic_read_enrichment.extract_barcode_from_image",
            return_value={
                "barcode": barcode,
                "barcode_type": "upc_a",
                "confidence": 0.95,
                "method": "local_decode",
                "crop_used": "bottom_left",
                "error": None,
            },
        ):
            with mock.patch(
                "app.services.p100_gpt_comic_read_enrichment.match_gpt_read_to_catalog",
            ) as catalog_match:
                from app.services.p100_gpt_catalog_match_service import P100CatalogMatch

                catalog_match.return_value = P100CatalogMatch(
                    matched=True,
                    catalog_issue_id=99,
                    method="text",
                    confidence=0.9,
                    series="Superman",
                    issue_number="39",
                )
                with mock.patch(
                    "app.services.p100_gpt_comic_read_enrichment.lookup_comicvine_by_barcode",
                    return_value={
                        "matched": True,
                        "source": "comicvine",
                        "comicvine_issue_id": "12345",
                        "series": "Superman",
                        "issue_number": "39",
                        "publisher": "DC",
                        "cover_date": None,
                        "name": None,
                        "image_url": None,
                        "raw": {},
                    },
                ):
                    payload = run_gpt_comic_read_enriched(session, _png_bytes())

    assert payload["final_match_source"] == "comicvine_barcode"
    assert payload["catalog_match"]["matched"] is True


def test_resolve_final_match_source_priority() -> None:
    cv = {"matched": True}
    cat = {"matched": True}
    assert resolve_final_match_source(comicvine_barcode_match=cv, catalog_match=cat) == "comicvine_barcode"
    assert (
        resolve_final_match_source(comicvine_barcode_match={"matched": False}, catalog_match=cat) == "catalog"
    )
    assert (
        resolve_final_match_source(comicvine_barcode_match={"matched": False}, catalog_match={"matched": False})
        == "gpt_only"
    )
