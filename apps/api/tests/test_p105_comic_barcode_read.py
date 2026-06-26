"""P105 comic barcode reconstruction, OCR retry, and correction tests."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from unittest.mock import patch

from PIL import Image, ImageDraw
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.services.barcode_validation_service import validate_barcode_catalog_match
from app.services.p105_comic_barcode_regions import (
    BarcodeCropConfig,
    FALLBACK_DETECTED_BOX_TOO_SMALL,
    FALLBACK_IMAGE_TOO_SMALL,
    FALLBACK_NO_VALID_PRICE_BOX_CONTOUR,
    FALLBACK_OPENCV_UNAVAILABLE,
    PriceBoxDetectionDiagnostics,
    compute_barcode_region_geometry,
    expand_box,
    opencv_import_status,
)
from app.services.p105_comic_barcode_read_service import (
    _correct_supplement_via_catalog,
    _main_upc_from_candidates,
    _reconstruct_full,
    _recover_supplement_from_catalog,
    publisher_validation_for_match,
    read_comic_barcode_from_image_bytes,
)
from app.services.p105_supplement_ocr import (
    OcrAttempt,
    hamming5,
    score_supplement_candidates,
)

MAIN = "761941341927"
SUPP_FULL = "03921"
FULL = MAIN + SUPP_FULL
MAIN2 = "761941343495"
SUPP2 = "00311"
FULL2 = MAIN2 + SUPP2


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_reconstruct_upc_plus_five_digit_supplement() -> None:
    assert _reconstruct_full(MAIN, SUPP_FULL) == FULL
    assert _reconstruct_full(MAIN2, SUPP2) == FULL2


def test_main_upc_from_candidates_extracts_12_digits_only() -> None:
    main, conf = _main_upc_from_candidates([FULL, MAIN])
    assert main == MAIN
    assert conf >= 0.9


def test_crop_expand_ratio_applied() -> None:
    box = expand_box(10, 20, 110, 80, 200, 200, expand_ratio=0.12)
    assert box[0] < 10 and box[1] < 20 and box[2] > 110 and box[3] > 80
    assert BarcodeCropConfig(expand_ratio=0.09).clamped_expand_ratio() == 0.10
    assert BarcodeCropConfig(expand_ratio=0.20).clamped_expand_ratio() == 0.15


def test_hamming5_substitution_distance() -> None:
    assert hamming5("03311", "00311") == 1
    assert hamming5("03921", "03921") == 0


def test_score_prefers_catalog_existing_candidate() -> None:
    attempts = [
        OcrAttempt(variant="a|psm7", raw_text="03311", digits="03311", confidence=0.8),
        OcrAttempt(variant="b|psm8", raw_text="03311", digits="03311", confidence=0.7),
        OcrAttempt(variant="c|psm7", raw_text="00311", digits="00311", confidence=0.6),
    ]
    scored = score_supplement_candidates(
        attempts,
        main_upc=MAIN,
        catalog_supplements={"00311": 42},
    )
    assert scored[0].digits == "00311"
    assert scored[0].catalog_exists is True


# ---------------------------------------------------------------------------
# Synthetic image
# ---------------------------------------------------------------------------


def _price_box_image(left_supplement: str) -> bytes:
    img = Image.new("RGB", (520, 360), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle((10, 200, 510, 340), fill=(255, 255, 255), outline=(40, 40, 40), width=2)
    draw.text((40, 255), left_supplement, fill=(0, 0, 0))
    for i in range(60):
        x = 190 + i * 4
        draw.rectangle((x, 220, x + 1, 320), fill=(0, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# OCR retry + correction integration
# ---------------------------------------------------------------------------


def _seed_catalog(session: Session, *, full_upc: str, publisher: str = "DC Comics") -> int:
    pub = CatalogPublisher(name=publisher, normalized_name=publisher.lower())
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id)
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number="39",
        normalized_issue_number="39",
        cover_date=date(2015, 4, 1),
    )
    session.add(issue)
    session.commit()
    session.add(CatalogUpc(issue_id=int(issue.id), upc=full_upc, normalized_upc=full_upc, source="test"))
    session.commit()
    return int(issue.id)


def _memory_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_ocr_substitution_03311_corrected_to_catalog_00311() -> None:
    """Expected 00311 but OCR returns 03311 → corrected via catalog, not blindly accepted."""
    image = _price_box_image("03311")
    session = _memory_session()
    _seed_catalog(session, full_upc=MAIN + "00311")

    def fake_variant(pil, label, *, psm, log_context):  # noqa: ANN001
        return OcrAttempt(variant=f"{label}|psm{psm}", raw_text="03311", digits="03311", confidence=0.82)

    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ), patch(
        "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
        return_value="",
    ), patch(
        "app.services.p105_supplement_ocr._ocr_variant",
        side_effect=fake_variant,
    ):
        result = read_comic_barcode_from_image_bytes(image, session=session)

    assert result.ocr_supplement == "03311"
    assert result.final_supplement == "00311"
    assert result.corrected_supplement == "00311"
    assert result.inferred_supplement is True
    assert result.catalog_confirmed is True
    assert result.auto_match_allowed is False
    assert "corrected" in result.correction_reason.lower()


def test_blank_first_crop_recovers_03921_via_retry_variants() -> None:
    """First crops blank; an upscaled retry variant recovers 03921."""
    image = _price_box_image("03921")

    def fake_variant(pil, label, *, psm, log_context):  # noqa: ANN001
        digits = "03921" if "upscale4x" in label else ""
        return OcrAttempt(
            variant=f"{label}|psm{psm}",
            raw_text=digits,
            digits=digits,
            confidence=0.8 if digits else 0.0,
        )

    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ), patch(
        "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
        return_value="",
    ), patch(
        "app.services.p105_supplement_ocr._ocr_variant",
        side_effect=fake_variant,
    ):
        result = read_comic_barcode_from_image_bytes(image, session=None)

    assert result.ocr_supplement == "03921"
    assert result.final_supplement == "03921"
    assert result.reconstructed_full == FULL


def test_bar_extension_disagreement_blocks_auto_match() -> None:
    """Bar decode supplement disagrees with OCR; OCR wins, auto-match blocked."""
    image = _price_box_image("03921")

    def fake_variant(pil, label, *, psm, log_context):  # noqa: ANN001
        return OcrAttempt(variant=f"{label}|psm{psm}", raw_text="03921", digits="03921", confidence=0.8)

    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ), patch(
        "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
        return_value="00111",
    ), patch(
        "app.services.p105_supplement_ocr._ocr_variant",
        side_effect=fake_variant,
    ):
        result = read_comic_barcode_from_image_bytes(image, session=None)

    assert result.decoded_supplement == "00111"
    assert result.ocr_supplement == "03921"
    assert result.final_supplement == "03921"
    assert result.supplement_disagreement is True
    assert result.auto_match_allowed is False


def test_debug_overlay_and_crops_generated(tmp_path, monkeypatch) -> None:
    image = _price_box_image("03921")
    monkeypatch.setattr(
        "app.services.p105_comic_barcode_regions.P105_BARCODE_DEBUG_ROOT",
        tmp_path,
    )

    def blank_variant(pil, label, *, psm, log_context):  # noqa: ANN001
        return OcrAttempt(variant=f"{label}|psm{psm}", raw_text="", digits="", confidence=0.0)

    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ), patch(
        "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
        return_value="",
    ), patch(
        "app.services.p105_supplement_ocr._ocr_variant",
        side_effect=blank_variant,
    ):
        result = read_comic_barcode_from_image_bytes(image, session=None, intake_item_id=7777)

    base = tmp_path / "7777"
    assert (base / "overlay.jpg").is_file()
    assert (base / "left_supplement.jpg").is_file()
    assert (base / "full_expanded.jpg").is_file()
    assert (base / "ocr_debug.json").is_file()
    assert (base / "left_variants").is_dir()
    assert any((base / "left_variants").iterdir())
    assert result.region_debug_path == str(base)

    # Overlay must be saved at ORIGINAL image size, not a thumbnail.
    with Image.open(base / "overlay.jpg") as ov:
        assert ov.size == (520, 360)
    # Crops saved at true size; left supplement must be a usable region.
    with Image.open(base / "left_supplement.jpg") as left:
        assert left.width > 40 and left.height > 40


def test_geometry_reports_dims_and_rectangles() -> None:
    with Image.open(BytesIO(_price_box_image("03921"))) as img:
        pil = img.convert("RGB")
    geo = compute_barcode_region_geometry(pil)
    data = geo.as_dict()
    assert data["original_size"] == {"width": 520, "height": 360}
    assert data["working_size"] == {"width": 520, "height": 360}
    rect = data["rectangles"]["left_supplement"]
    assert rect["width"] > 40 and rect["height"] > 40
    assert geo.geometry_failed is False
    # report_lines should mention every region.
    text = "\n".join(geo.report_lines())
    for name in ("full_expanded", "main_bars", "left_supplement", "right_cover_digit"):
        assert name in text


def test_tiny_detected_price_box_falls_back_to_percentage() -> None:
    with Image.open(BytesIO(_price_box_image("03921"))) as img:
        pil = img.convert("RGB")
    tiny_box = (5, 5, 17, 14)  # 12x9 px — the catastrophic real-world case
    fake_det = PriceBoxDetectionDiagnostics(
        box=tiny_box,
        deskew_angle=0.0,
        detection_size=(520, 200),
        detection_scale=1.0,
        opencv_available=True,
        contour_count=3,
        area_candidate_count=1,
        aspect_candidate_count=1,
        chosen_candidate={"x": 5, "y": 5, "width": 12, "height": 9, "selected": True},
    )
    with patch(
        "app.services.p105_comic_barcode_regions._detect_price_box",
        return_value=fake_det,
    ):
        geo = compute_barcode_region_geometry(pil)
    assert geo.detection_method == "percentage"
    assert geo.fallback_reason == FALLBACK_DETECTED_BOX_TOO_SMALL
    assert geo.geometry_rejection_reason == FALLBACK_DETECTED_BOX_TOO_SMALL
    assert geo.price_box is None
    assert geo.left_supplement[2] - geo.left_supplement[0] >= 40
    assert geo.left_supplement[3] - geo.left_supplement[1] >= 40
    assert geo.geometry_failed is False


def test_thumbnail_input_flags_geometry_failed() -> None:
    thumb = Image.new("RGB", (40, 20), (255, 255, 255))
    buf = BytesIO()
    thumb.save(buf, format="JPEG")

    def blank_variant(pil, label, *, psm, log_context):  # noqa: ANN001
        return OcrAttempt(variant=f"{label}|psm{psm}", raw_text="", digits="", confidence=0.0)

    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=("", 0.0),
    ), patch(
        "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
        return_value="",
    ), patch(
        "app.services.p105_supplement_ocr._ocr_variant",
        side_effect=blank_variant,
    ):
        result = read_comic_barcode_from_image_bytes(buf.getvalue(), session=None)

    geom = result.region_ocr_debug["geometry"]
    assert geom["geometry_failed"] is True
    assert geom["original_size"] == {"width": 40, "height": 20}
    assert geom.get("fallback_reason") == FALLBACK_IMAGE_TOO_SMALL
    reason = result.review_reason.lower()
    assert "too small for reliable barcode ocr" in reason
    assert "original_size=40x20" in reason
    assert result.auto_match_allowed is False


def test_debug_dir_param_writes_manual_outputs(tmp_path) -> None:
    """The CLI path: debug_dir writes overlay + attempts without intake item id."""
    image = _price_box_image("03921")
    out_dir = tmp_path / "manual_run"

    def blank_variant(pil, label, *, psm, log_context):  # noqa: ANN001
        return OcrAttempt(variant=f"{label}|psm{psm}", raw_text="", digits="", confidence=0.0)

    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ), patch(
        "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
        return_value="",
    ), patch(
        "app.services.p105_supplement_ocr._ocr_variant",
        side_effect=blank_variant,
    ):
        result = read_comic_barcode_from_image_bytes(image, session=None, debug_dir=out_dir)

    assert result.region_debug_path == str(out_dir)
    assert (out_dir / "overlay.jpg").is_file()
    assert (out_dir / "left_supplement.jpg").is_file()
    assert (out_dir / "ocr_debug.json").is_file()


def test_correct_supplement_via_catalog_single_candidate() -> None:
    session = _memory_session()
    issue_id = _seed_catalog(session, full_upc=MAIN + "00311")
    catalog_map = {"00311": issue_id}
    corrected = _correct_supplement_via_catalog(
        session,
        main_upc=MAIN,
        ocr_digits="03311",
        catalog_map=catalog_map,
        cover_path=None,
    )
    assert corrected is not None
    supp, returned_issue, _fp, dist = corrected
    assert supp == "00311"
    assert returned_issue == issue_id
    assert dist == 1


def test_fallback_reason_opencv_unavailable() -> None:
    pil = Image.new("RGB", (800, 1200), color=(120, 120, 120))
    det = PriceBoxDetectionDiagnostics(
        opencv_available=False,
        exception_message="ImportError: cv2",
        detection_size=(800, 600),
    )
    with patch("app.services.p105_comic_barcode_regions._detect_price_box", return_value=det):
        geo = compute_barcode_region_geometry(pil)
    assert geo.detection_method == "percentage"
    assert geo.fallback_reason == FALLBACK_OPENCV_UNAVAILABLE
    assert geo.opencv_available is False


def test_fallback_reason_image_too_small() -> None:
    pil = Image.new("RGB", (40, 20), color=(255, 255, 255))
    geo = compute_barcode_region_geometry(pil)
    assert geo.detection_method == "percentage"
    assert geo.fallback_reason == FALLBACK_IMAGE_TOO_SMALL


def test_fallback_reason_no_valid_price_box_contour() -> None:
    pil = Image.new("RGB", (520, 360), color=(40, 40, 40))
    det = PriceBoxDetectionDiagnostics(
        opencv_available=True,
        contour_count=6,
        area_candidate_count=2,
        aspect_candidate_count=0,
        detection_size=(520, 200),
        candidate_boxes=[
            {"x": 1, "y": 2, "width": 80, "height": 80, "passes_area": True, "passes_aspect": False},
        ],
    )
    with patch("app.services.p105_comic_barcode_regions._detect_price_box", return_value=det):
        geo = compute_barcode_region_geometry(pil)
    assert geo.detection_method == "percentage"
    assert geo.fallback_reason == FALLBACK_NO_VALID_PRICE_BOX_CONTOUR


def test_opencv_import_status_reports_availability() -> None:
    ok, err = opencv_import_status()
    assert ok is True or ok is False
    if not ok:
        assert err


def test_geometry_overlay_runs_on_synthetic_image() -> None:
    with Image.open(BytesIO(_price_box_image("03921"))) as img:
        pil = img.convert("RGB")
    geometry = compute_barcode_region_geometry(pil)
    assert geometry.left_supplement[2] > geometry.left_supplement[0]
    assert geometry.main_bars[2] > geometry.main_bars[0]
    assert geometry.detection_method in {"geometry", "percentage"}


# ---------------------------------------------------------------------------
# Publisher / catalog guards (unchanged behavior)
# ---------------------------------------------------------------------------


def test_publisher_prefix_mismatch_forces_review_message() -> None:
    reason = publisher_validation_for_match(FULL, publisher="Marvel", issue_number="39", year="2015")
    assert reason
    assert (
        validate_barcode_catalog_match(FULL, publisher="Marvel", issue_number="39", year="2015").status
        == "no_safe_match"
    )


def test_catalog_recovery_infers_missing_first_digit() -> None:
    session = _memory_session()
    issue_id = _seed_catalog(session, full_upc=FULL)
    with patch(
        "app.services.p105_comic_barcode_read_service.fingerprint_match_score_for_crop_path",
        return_value=85.0,
    ):
        supp, returned_issue, conf = _recover_supplement_from_catalog(
            session,
            main_upc=MAIN,
            partial_supplement="3921",
            cover_path=None,
        )
    assert supp == SUPP_FULL
    assert returned_issue == issue_id
    assert conf >= 0.85
