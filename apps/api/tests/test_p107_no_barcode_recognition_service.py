"""Unit tests for P107 no-barcode recognition scoring and pipeline."""

from __future__ import annotations

import pytest
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.services.p107_no_barcode_recognition_service import (
    P107ExtractedSignals,
    decision_from_score,
    load_p107_manifest,
    recognize_cover_without_barcode,
    score_p107_match,
    seed_catalog_for_p107_tests,
)
from app.services.photo_import_storage_service import REPO_ROOT


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def test_score_weights_are_deterministic() -> None:
    signals = P107ExtractedSignals(
        title_candidates=["Astro City"],
        issue_number_candidates=["4"],
        publisher_candidates=["Image"],
        year_candidates=[1995],
    )
    candidate = {
        "catalog_issue_id": 1,
        "series": "Astro City",
        "issue_number": "4",
        "publisher": "Image",
        "year": "1995",
    }
    score = score_p107_match(candidate, signals=signals, fingerprint_score=100.0)
    assert score == 100.0


def test_decision_thresholds() -> None:
    assert decision_from_score(95.0) == "auto_match"
    assert decision_from_score(94.9) == "needs_review_top_3"
    assert decision_from_score(80.0) == "needs_review_top_3"
    assert decision_from_score(79.9) == "needs_review"


def test_load_default_manifest() -> None:
    rows = load_p107_manifest(REPO_ROOT / "data" / "p107" / "no_barcode_manifest.csv")
    assert len(rows) == 4
    assert rows[0]["expected_title"] == "The Ferret"


def test_recognize_skips_when_barcode_detected(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    img = tmp_path / "cover.jpg"
    Image.new("RGB", (400, 600), color=(10, 10, 10)).save(img, format="JPEG")
    engine = _engine()
    with Session(engine) as session:
        monkeypatch.setattr(
            "app.services.p107_no_barcode_recognition_service._barcode_detected_on_image",
            lambda _b: (True, "76194134192701911"),
        )
        result = recognize_cover_without_barcode(session, img)
        assert result["barcode_detected"] is True
        assert result["decision"] == "barcode_present_skip"


def test_recognize_pipeline_with_seeded_catalog(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    img = tmp_path / "astro.jpg"
    Image.new("RGB", (640, 960), color=(20, 20, 30)).save(img, format="JPEG")
    engine = _engine()
    with Session(engine) as session:
        seed_catalog_for_p107_tests(session)
        monkeypatch.setattr(
            "app.services.p107_no_barcode_recognition_service._barcode_detected_on_image",
            lambda _b: (False, None),
        )
        monkeypatch.setattr(
            "app.services.p107_no_barcode_recognition_service.extract_ocr_signal",
            lambda *a, **k: type(
                "O",
                (),
                {
                    "raw_text": "ASTRO CITY #4 IMAGE 1995",
                    "normalized_text": "ASTRO CITY 4",
                    "title": "Astro City",
                    "issue_number": "4",
                    "publisher": "Image",
                    "variant": None,
                    "confidence": 0.9,
                },
            )(),
        )
        monkeypatch.setattr(
            "app.services.p107_no_barcode_recognition_service.search_catalog_fingerprint_hits_for_crop_path",
            lambda *a, **k: [],
        )
        monkeypatch.setattr(
            "app.services.p107_no_barcode_recognition_service.fingerprint_match_score_for_crop_path",
            lambda *a, **k: 85.0,
        )
        expected = {
            "expected_title": "Astro City",
            "expected_issue_number": "4",
            "expected_publisher": "Image",
            "expected_year": "1995",
        }
        result = recognize_cover_without_barcode(session, img, expected=expected)
        assert result["barcode_detected"] is False
        assert result["best_match"] is not None
        assert result["confidence"] >= 80.0
        assert result["decision"] in {"auto_match", "needs_review_top_3"}
