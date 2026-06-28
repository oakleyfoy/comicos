"""P107 benchmark suite runner tests."""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.services.p107_no_barcode_recognition_service import (
    load_p107_manifest,
    run_p107_benchmark,
    seed_catalog_for_p107_tests,
)
from app.services.photo_import_storage_service import REPO_ROOT


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def test_run_benchmark_counts_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = REPO_ROOT / "data" / "p107" / "no_barcode_manifest.csv"
    engine = _engine()

    def fake_recognize(session, image_path, **kwargs):
        return {
            "barcode_detected": False,
            "ocr_tokens": [],
            "visual_fingerprint": "",
            "candidate_queries": [],
            "ranked_matches": [],
            "best_match": None,
            "confidence": 0.0,
            "decision": "needs_review",
            "error": "image_not_found:test",
        }

    monkeypatch.setattr(
        "app.services.p107_no_barcode_recognition_service.recognize_cover_without_barcode",
        fake_recognize,
    )
    with Session(engine) as session:
        seed_catalog_for_p107_tests(session)
        report = run_p107_benchmark(session, manifest_path=manifest, limit=2)
    assert report["rows"] == 2
    assert report["missing_images"] == 2
    assert len(report["evaluations"]) == 2


def test_manifest_path_relative_to_api_root() -> None:
    path = REPO_ROOT / "data" / "p107" / "no_barcode_manifest.csv"
    assert path.is_file()
