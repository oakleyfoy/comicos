from app.services.catalog_cover_ocr_service import (
    MISSING_LOCAL_IMAGE,
    MISSING_TESSERACT_BINARY,
    OCR_EMPTY_RESULT,
    OCR_EXCEPTION,
    classify_ocr_skip_bucket,
)
from app.services.catalog_bulk_ocr_service import OcrSkipBreakdown


def test_classify_ocr_skip_bucket():
    assert classify_ocr_skip_bucket(MISSING_TESSERACT_BINARY) == "skipped_missing_tesseract"
    assert classify_ocr_skip_bucket(MISSING_LOCAL_IMAGE) == "skipped_missing_file"
    assert classify_ocr_skip_bucket(OCR_EMPTY_RESULT) == "skipped_empty_text"
    assert classify_ocr_skip_bucket(OCR_EXCEPTION) == "skipped_image_load_error"


def test_ocr_skip_breakdown_as_dict():
    b = OcrSkipBreakdown()
    b.record("skipped_empty_text")
    b.record("skipped_missing_tesseract")
    d = b.as_dict()
    assert d["skipped_empty_text"] == 1
    assert d["skipped_missing_tesseract"] == 1
    assert d["skipped_existing_ocr"] == 0
