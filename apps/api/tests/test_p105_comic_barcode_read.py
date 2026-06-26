"""P105 comic barcode reconstruction and guard tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from io import BytesIO

import pytest
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.services.barcode_validation_service import validate_barcode_catalog_match
from app.services.p105_comic_barcode_regions import BarcodeCropConfig, expand_box
from app.services.p105_comic_barcode_read_service import (
    _reconstruct_full,
    _recover_supplement_from_catalog,
    read_comic_barcode_from_image_bytes,
)
from app.services.p105_comic_barcode_read_service import publisher_validation_for_match

MAIN = "761941341927"
SUPP_FULL = "03921"
FULL = MAIN + SUPP_FULL
MAIN2 = "761941343495"
SUPP2 = "00311"
FULL2 = MAIN2 + SUPP2


def test_reconstruct_upc_plus_five_digit_supplement() -> None:
    assert _reconstruct_full(MAIN, SUPP_FULL) == FULL
    assert _reconstruct_full(MAIN2, SUPP2) == FULL2


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


def test_partial_supplement_refuses_auto_match_flag() -> None:
    with patch(
        "app.services.p105_comic_barcode_read_service._decode_main_upc_from_pil",
        return_value=(MAIN, 0.95),
    ):
        with patch(
            "app.services.p105_comic_barcode_read_service._vision_ocr_region",
            side_effect=[("3921", 0.8), ("", 0.0)],
        ):
            result = read_comic_barcode_from_image_bytes(_tiny_jpeg(), session=None)
    assert result.main_upc == MAIN
    assert result.left_supplement_ocr == "03921" or result.left_supplement_ocr == "3921"
    assert result.auto_match_allowed is False
    assert "3–4" in result.review_reason or result.inferred_supplement or not result.auto_match_allowed


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
