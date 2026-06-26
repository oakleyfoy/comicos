"""P105 comic barcode reconstruction and guard tests."""

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
from app.services.p105_comic_barcode_regions import BarcodeCropConfig, expand_box
from app.services.p105_comic_barcode_read_service import (
    _choose_final_supplement,
    _main_upc_from_candidates,
    _reconstruct_full,
    _recover_supplement_from_catalog,
    read_comic_barcode_from_image_bytes,
    publisher_validation_for_match,
)

MAIN = "761941341927"
SUPP_FULL = "03921"
FULL = MAIN + SUPP_FULL
MAIN2 = "761941343495"
SUPP2 = "00311"
FULL2 = MAIN2 + SUPP2


def test_reconstruct_upc_plus_five_digit_supplement() -> None:
    assert _reconstruct_full(MAIN, SUPP_FULL) == FULL
    assert _reconstruct_full(MAIN2, SUPP2) == FULL2


def test_main_upc_from_candidates_ignores_merged_17_without_splitting() -> None:
    main, conf = _main_upc_from_candidates([FULL, MAIN])
    assert main == MAIN
    assert conf >= 0.9


def test_crop_expand_ratio_applied() -> None:
    box = expand_box(10, 20, 110, 80, 200, 200, expand_ratio=0.12)
    assert box[0] < 10
    assert box[1] < 20
    assert box[2] > 110
    assert box[3] > 80
    cfg = BarcodeCropConfig(expand_ratio=0.09)
    assert cfg.clamped_expand_ratio() == 0.10
    cfg2 = BarcodeCropConfig(expand_ratio=0.20)
    assert cfg2.clamped_expand_ratio() == 0.15


def _tiny_jpeg() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (120, 160), color="white").save(buf, format="JPEG")
    return buf.getvalue()


def _synthetic_price_box(left_supplement: str) -> bytes:
    img = Image.new("RGB", (520, 200), (235, 235, 235))
    draw = ImageDraw.Draw(img)
    draw.rectangle((4, 4, 515, 195), outline=(60, 60, 60), width=2)
    draw.text((24, 82), left_supplement, fill=(0, 0, 0))
    for i in range(48):
        x = 168 + i * 5
        draw.rectangle((x, 48, x + 2, 152), fill=(0, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_partial_supplement_refuses_auto_match_flag() -> None:
    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ):
        with patch(
            "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
            return_value="",
        ):
            with patch(
                "app.services.p105_comic_barcode_read_service._tesseract_supplement_ocr",
                return_value=("3921", 0.8, "3921"),
            ):
                with patch(
                    "app.services.p105_comic_barcode_read_service._vision_ocr_region",
                    side_effect=[("", 0.0), ("", 0.0)],
                ):
                    result = read_comic_barcode_from_image_bytes(_tiny_jpeg(), session=None)
    assert result.main_upc == MAIN
    assert result.ocr_supplement == "3921"
    assert result.auto_match_allowed is False
    assert result.inferred_supplement or "3–4" in result.review_reason


def test_ocr_supplement_fixture_03921_overrides_bar_decode() -> None:
    image = _synthetic_price_box(SUPP_FULL)
    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ):
        with patch(
            "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
            return_value="00111",
        ):
            with patch(
                "app.services.p105_comic_barcode_read_service._tesseract_supplement_ocr",
                return_value=(SUPP_FULL, 0.85, SUPP_FULL),
            ):
                with patch(
                    "app.services.p105_comic_barcode_read_service._vision_ocr_region",
                    side_effect=[("", 0.0), ("", 0.0)],
                ):
                    result = read_comic_barcode_from_image_bytes(image, session=None, intake_item_id=9001)
    assert result.ocr_supplement == SUPP_FULL
    assert result.final_supplement == SUPP_FULL
    assert result.decoded_supplement == "00111"
    assert result.supplement_disagreement is True
    assert result.reconstructed_full == FULL
    assert result.auto_match_allowed is False


def test_ocr_supplement_fixture_00311_overrides_bar_decode() -> None:
    image = _synthetic_price_box(SUPP2)
    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN2, 0.95),
    ):
        with patch(
            "app.services.p105_comic_barcode_read_service._decode_supplement_from_pil",
            return_value="00841",
        ):
            with patch(
                "app.services.p105_comic_barcode_read_service._tesseract_supplement_ocr",
                return_value=(SUPP2, 0.84, SUPP2),
            ):
                with patch(
                    "app.services.p105_comic_barcode_read_service._vision_ocr_region",
                    side_effect=[("", 0.0), ("", 0.0)],
                ):
                    result = read_comic_barcode_from_image_bytes(image, session=None)
    assert result.final_supplement == SUPP2
    assert result.decoded_supplement == "00841"
    assert result.supplement_disagreement is True


def test_choose_final_supplement_rejects_bar_only_without_ocr() -> None:
    final, disagreement, inferred, reason, recovery = _choose_final_supplement(
        main_upc=MAIN,
        ocr_supplement="",
        ocr_conf=0.0,
        decoded_supplement="00111",
        session=None,
        cover_path=None,
    )
    assert final == ""
    assert disagreement is False
    assert "without confirming left OCR" in reason


def test_publisher_prefix_mismatch_forces_review_message() -> None:
    reason = publisher_validation_for_match(FULL, publisher="Marvel", issue_number="39", year="2015")
    assert reason
    assert validate_barcode_catalog_match(FULL, publisher="Marvel", issue_number="39", year="2015").status == "no_safe_match"


def test_catalog_recovery_infers_missing_first_digit() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
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
        session.add(
            CatalogUpc(issue_id=int(issue.id), upc=FULL, normalized_upc=FULL, source="test")
        )
        session.commit()
        with patch(
            "app.services.p105_comic_barcode_read_service.fingerprint_match_score_for_crop_path",
            return_value=85.0,
        ):
            supp, issue_id, conf = _recover_supplement_from_catalog(
                session,
                main_upc=MAIN,
                partial_supplement="3921",
                cover_path=None,
            )
    assert supp == SUPP_FULL
    assert issue_id is not None
    assert conf >= 0.85
