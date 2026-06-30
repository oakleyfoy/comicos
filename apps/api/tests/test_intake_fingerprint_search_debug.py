"""Fingerprint search debug bundles, logging, and cross-publisher guardrails."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.catalog_master import CatalogImage, CatalogImageFingerprint, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.intake_fingerprint_search_debug_service import (
    FingerprintSearchDebugContext,
    build_fingerprint_search_details,
    execute_catalog_fingerprint_search,
    filter_cross_publisher_fingerprint_review_rows,
    fingerprint_search_debug_context,
    write_fingerprint_search_debug_bundle,
)
from app.services.p106_fingerprint_review_fallback_service import attach_fingerprint_review_to_diagnosis
from app.services.p106_1_gcd_non_barcode_recovery_service import IntakeGcdRecoveryHints, FingerprintRecoveryCandidate


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _jpeg(path: Path, size=(800, 1200)) -> Path:
    Image.new("RGB", size, color=(10, 20, 30)).save(path, format="JPEG")
    return path


def test_debug_bundle_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.intake_fingerprint_search_debug_service as dbg

    monkeypatch.setattr(dbg, "REPO_ROOT", tmp_path)
    img = _jpeg(tmp_path / "cover.jpg")
    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
        session.add(pub)
        session.flush()
        series = CatalogSeries(name="X", normalized_name="x", publisher_id=int(pub.id))
        session.add(series)
        session.flush()
        issue = CatalogIssue(
            series_id=int(series.id),
            publisher_id=int(pub.id),
            issue_number="1",
            normalized_issue_number="1",
        )
        session.add(issue)
        session.flush()
        image = CatalogImage(
            issue_id=int(issue.id),
            local_path=str(img),
            source_url="http://example/cover.jpg",
            source="test",
        )
        session.add(image)
        session.flush()
        phash, dhash, ahash = ("0" * 64, "1" * 64, "0" * 64)
        session.add(
            CatalogImageFingerprint(
                image_id=int(image.id),
                issue_id=int(issue.id),
                phash=phash,
                dhash=dhash,
                ahash=ahash,
                colorhash="abc",
            )
        )
        session.commit()
        ctx = FingerprintSearchDebugContext(intake_item_id=42, barcode="75960620629200111")
        with fingerprint_search_debug_context(ctx):
            execute_catalog_fingerprint_search(session, crop_path=img, limit=5)
    bundle = tmp_path / "data" / "debug" / "fingerprint" / "item_42"
    assert (bundle / "search_image.jpg").is_file()
    assert (bundle / "search_fingerprint.json").is_file()
    payload = json.loads((bundle / "search_fingerprint.json").read_text(encoding="utf-8"))
    assert payload["search"]["sha256"]
    assert payload["search"]["phash"]


def test_cross_publisher_fingerprint_review_suppressed() -> None:
    rows = [
        {"publisher": "DC Comics", "series": "Superman", "issue_number": "21", "confidence": 0.9},
    ]
    filtered, reason = filter_cross_publisher_fingerprint_review_rows(
        barcode="75960620629200111",
        rows=rows,
        hints_publisher="Marvel",
    )
    assert filtered == []
    assert reason == "cross_publisher_visual_mismatch"


def test_attach_fingerprint_review_sets_conflict_for_cross_publisher(session: Session) -> None:
    session.add(User(id=1, email="u2@example.com", password_hash="x"))
    pub = CatalogPublisher(name="DC", normalized_name="dc")
    session.add(pub)
    session.flush()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=int(pub.id))
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="21",
        normalized_issue_number="21",
    )
    session.add(issue)
    session.commit()
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series=None,
        issue_number=None,
        year=None,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        fingerprint_region_safe=True,
        fingerprint_candidates=[
            FingerprintRecoveryCandidate(
                catalog_issue_id=int(issue.id),
                gcd_issue_id=None,
                confidence=0.95,
                match_source="catalog_fingerprint",
            )
        ],
    )
    diagnosis: dict = {}
    attach_fingerprint_review_to_diagnosis(
        session,
        diagnosis,
        hints=hints,
        barcode="75960620629200111",
    )
    assert diagnosis.get("fingerprint_conflict_reason") == "cross_publisher_visual_mismatch"
    assert "needs_review_top_candidates" not in diagnosis


@pytest.fixture
def session() -> Session:
    engine = _engine()
    with Session(engine) as s:
        yield s


def test_debug_fingerprint_match_script_writes_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib.util
    import sys

    import app.services.intake_fingerprint_search_debug_service as dbg

    monkeypatch.setattr(dbg, "REPO_ROOT", tmp_path)
    img = _jpeg(tmp_path / "cli_cover.jpg")
    db_path = tmp_path / "cli.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    class _Settings:
        database_url = f"sqlite:///{db_path.as_posix()}"

    monkeypatch.setattr("app.core.config.get_settings", lambda: _Settings())
    script = Path(__file__).resolve().parents[1] / "scripts" / "debug_fingerprint_match.py"
    spec = importlib.util.spec_from_file_location("debug_fingerprint_match", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "debug_fingerprint_match.py",
            "--image",
            str(img),
            "--limit",
            "5",
            "--intake-item-id",
            "99",
        ],
    )
    mod.main()
    out = capsys.readouterr()
    assert "phash" in out.out
    bundle = tmp_path / "data" / "debug" / "fingerprint" / "item_99"
    assert (bundle / "search_image.jpg").is_file()
    assert (bundle / "search_fingerprint.json").is_file()
