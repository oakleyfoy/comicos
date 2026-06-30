"""Full-cover follow-up when barcode reads on UPC/barcode crops but GCD/catalog miss."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.intake_queue import (
    ITEM_AUTO_MATCHED,
    ITEM_NEEDS_FULL_COVER_PHOTO,
    ITEM_QUEUED,
    IntakeItemCandidate,
    IntakeSession,
    IntakeSessionItem,
)
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.intake_fingerprint_image_region_service import (
    REGION_BARCODE_STRIP,
    REGION_FULL_COVER,
    REGION_UNSAFE_PARTIAL_COVER,
    assess_fingerprint_image_region,
)
from app.services.p105_comic_barcode_regions import BarcodeRegionGeometry
from app.services.p106_fingerprint_review_fallback_service import (
    attach_fingerprint_review_to_diagnosis,
    persist_review_candidates_on_intake_item,
)
from app.services.p106_1_gcd_non_barcode_recovery_service import (
    FingerprintRecoveryCandidate,
    IntakeGcdRecoveryHints,
    gather_intake_gcd_recovery_hints,
)
from app.services.intake_full_cover_followup_service import (
    FULL_COVER_USER_MESSAGE,
    apply_full_cover_followup_to_diagnosis,
    should_require_full_cover_followup,
)
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
import app.services.intake_worker_service as worker

MARVEL_BC = "75960620629200111"


def _tall_left_edge_geometry(*, width: int = 1080, height: int = 1920) -> BarcodeRegionGeometry:
    """Production-shaped tall phone capture: vertical barcode column on the left."""
    fe = (0, 0, width, int(height * 0.55))
    mb = (0, int(height * 0.12), int(width * 0.28), int(height * 0.88))
    ls = (0, int(height * 0.12), int(width * 0.30), int(height * 0.88))
    rc = (int(width * 0.78), int(height * 0.12), width, int(height * 0.88))
    return BarcodeRegionGeometry(
        full_expanded=fe,
        main_bars=mb,
        left_supplement=ls,
        right_cover_digit=rc,
        original_size=(width, height),
    )


def _full_cover_phone_geometry(*, width: int = 800, height: int = 1200) -> BarcodeRegionGeometry:
    fe = (0, int(height * 0.52), width, height)
    mb = (int(width * 0.16), int(height * 0.55), int(width * 0.74), height)
    ls = (0, int(height * 0.58), int(width * 0.30), int(height * 0.82))
    rc = (int(width * 0.74), int(height * 0.58), width, int(height * 0.82))
    return BarcodeRegionGeometry(
        full_expanded=fe,
        main_bars=mb,
        left_supplement=ls,
        right_cover_digit=rc,
        original_size=(width, height),
    )


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _empty_marvel_gcd_db(tmp_path: Path) -> Path:
    path = tmp_path / "gcd.sqlite"
    engine = gcd_engine_from(str(path))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE gcd_series (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE gcd_issue (id INTEGER PRIMARY KEY, number TEXT, barcode TEXT, key_date TEXT, "
                "series_id INTEGER, title TEXT, notes TEXT)"
            )
        )
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'Marvel')"))
        conn.execute(
            text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (1, 'X-Men', 2024, 1)")
        )
        conn.execute(
            text(
                "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                "VALUES (88100, '1', NULL, '2024-06-00', 1, 'Issue', '')"
            )
        )
    return path


def _patch_gcd(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    import app.services.gcd_catalog_import_dashboard_service as gcd_dash

    monkeypatch.setattr(gcd_dash, "resolve_gcd_path", lambda override=None: path)
    monkeypatch.setattr(gcd_dash, "resolve_cache_path", lambda override=None: None)


def _worker_mocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    barcode: str,
    image_size: tuple[int, int] = (900, 280),
) -> Path:
    from PIL import Image

    img = tmp_path / "scan.jpg"
    Image.new("RGB", image_size, color=(4, 4, 4)).save(img, format="JPEG")
    supp = barcode[12:17]
    monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
    monkeypatch.setattr(
        worker,
        "read_comic_barcode_from_image_bytes",
        lambda *a, **k: ComicBarcodeReadResult(
            main_upc=barcode[:12],
            reconstructed_full=barcode,
            final_supplement=supp,
            decoded_supplement=supp,
            supplement_decode_confidence=0.99,
            confidence_main=0.95,
        ),
    )
    monkeypatch.setattr(
        worker,
        "evaluate_cover_fingerprint_vs_barcode",
        lambda *a, **k: CoverFingerprintOutcome(
            blocks_auto_match=False,
            info_message=None,
            fingerprint_issue_id=None,
            fingerprint_confidence=None,
            disagrees=False,
        ),
    )
    return img


def test_barcode_strip_region_detected() -> None:
    region = assess_fingerprint_image_region(None, image_bytes=_jpeg_bytes(900, 280))
    assert region.fingerprint_image_region == REGION_BARCODE_STRIP
    assert region.fingerprint_region_safe is False
    assert region.fingerprint_suppressed_reason


def test_full_cover_region_safe() -> None:
    region = assess_fingerprint_image_region(
        None,
        image_bytes=_jpeg_bytes(800, 1200),
        geometry=_full_cover_phone_geometry(width=800, height=1200),
    )
    assert region.fingerprint_region_safe is True
    assert region.fingerprint_image_region == REGION_FULL_COVER


def test_tall_partial_cover_left_barcode_frame_unsafe() -> None:
    region = assess_fingerprint_image_region(
        None,
        image_bytes=_jpeg_bytes(1080, 1920),
        geometry=_tall_left_edge_geometry(width=1080, height=1920),
    )
    assert region.fingerprint_image_region == REGION_UNSAFE_PARTIAL_COVER
    assert region.fingerprint_region_safe is False
    assert region.fingerprint_suppressed_reason == "unsafe_partial_cover_barcode_frame"


def test_unsafe_region_never_persists_fingerprint_candidates() -> None:
    cleared: list[int] = []

    def _clear(_session, item_id: int) -> None:
        cleared.append(item_id)

    def _add(*args, **kwargs) -> None:
        raise AssertionError("must not add fingerprint candidates")

    diagnosis = {
        "fingerprint_region_safe": False,
        "fingerprint_image_region": REGION_UNSAFE_PARTIAL_COVER,
        "needs_review_top_candidates": [{"catalog_issue_id": 1, "confidence": 0.9}],
    }
    persist_review_candidates_on_intake_item(
        MagicMock(),
        item_id=99,
        diagnosis=diagnosis,
        add_candidate_fn=_add,
        clear_candidates_fn=_clear,
    )
    assert cleared == [99]
    assert "needs_review_top_candidates" in diagnosis


def test_tall_partial_cover_worker_requires_full_cover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from app.services.intake_p106_1_intake_debug_service import p106_1_intake_debug_dir

    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda *a, **k: None)
    img = _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(1080, 1920))

    tall_geo = _tall_left_edge_geometry(width=1080, height=1920)

    def _fixed_geometry(pil, **kwargs):
        return tall_geo

    monkeypatch.setattr(
        "app.services.p105_comic_barcode_regions.compute_barcode_region_geometry",
        _fixed_geometry,
    )

    debug_item_id = 759607
    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        intake = IntakeSession(
            user_id=1,
            session_token="tok-tall",
            status="active",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(
            id=debug_item_id,
            session_id=int(intake.id),
            user_id=1,
            storage_path=str(img.name),
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()
        final = worker.process_intake_item(session, item_id=debug_item_id)
        assert final == ITEM_NEEDS_FULL_COVER_PHOTO

    region_json = p106_1_intake_debug_dir(intake_item_id=debug_item_id) / "region_debug.json"
    assert region_json.is_file()
    meta = json.loads(region_json.read_text(encoding="utf-8"))
    assert meta["fingerprint_image_region"] == REGION_UNSAFE_PARTIAL_COVER
    assert meta["full_cover_followup_required"] is True
    assert meta["p106_1_review_candidates_count"] == 0


def _jpeg_bytes(w: int, h: int) -> bytes:
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (w, h), color=(1, 2, 3)).save(buf, format="JPEG")
    return buf.getvalue()


def test_gather_hints_suppresses_fingerprint_on_barcode_strip(tmp_path: Path) -> None:
    engine = _engine()
    img = tmp_path / "strip.jpg"
    img.write_bytes(_jpeg_bytes(900, 280))

    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        session.commit()
        item = IntakeSessionItem(
            session_id=1,
            user_id=1,
            storage_path="x.jpg",
            status=ITEM_QUEUED,
        )
        hints = gather_intake_gcd_recovery_hints(
            session,
            item=item,
            normalized_barcode=MARVEL_BC,
            image_path=img,
            image_bytes=img.read_bytes(),
            p105=None,
        )
        assert hints.fingerprint_region_safe is False
        assert hints.fingerprint_candidates == []


class _FakeHit:
    def __init__(self, issue_id: int, confidence: float) -> None:
        self.issue_id = issue_id
        self.confidence = confidence


def test_attach_fingerprint_review_skipped_when_region_unsafe() -> None:
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series="X-Men",
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        fingerprint_candidates=[
            FingerprintRecoveryCandidate(
                catalog_issue_id=1,
                gcd_issue_id=None,
                confidence=0.95,
                match_source="catalog_image_fingerprint",
            )
        ],
        fingerprint_region_safe=False,
        fingerprint_suppressed_reason="barcode_region_crop",
    )
    diagnosis: dict = {"gcd_match_count": 0}
    attach_fingerprint_review_to_diagnosis(MagicMock(), diagnosis, hints=hints, barcode=MARVEL_BC)
    assert "needs_review_top_candidates" not in diagnosis


def test_apply_full_cover_clears_fingerprint_candidates() -> None:
    region = assess_fingerprint_image_region(None, image_bytes=_jpeg_bytes(900, 280))
    diagnosis = {
        "gcd_match_count": 0,
        "needs_review_top_candidates": [{"catalog_issue_id": 1}],
        "review_decision": "needs_review_top_candidates",
    }
    apply_full_cover_followup_to_diagnosis(diagnosis, region)
    assert diagnosis.get("needs_full_cover_photo") is True
    assert "needs_review_top_candidates" not in diagnosis
    assert diagnosis.get("fingerprint_region_safe") is False


def test_should_require_full_cover_on_gcd_miss_and_strip() -> None:
    region = assess_fingerprint_image_region(None, image_bytes=_jpeg_bytes(900, 280))
    assert should_require_full_cover_followup(
        gap_diag={"gcd_match_count": 0, "reason": "no_gcd_barcode_match"},
        primary_region=region,
        recognition_region=region,
        has_full_cover_image=False,
        local_catalog_hit=False,
        p106_exact_barcode_authority=False,
        barcode_decoded=True,
    )


def test_should_require_full_cover_when_p106_1_pool_but_no_barcode_hit() -> None:
    region = assess_fingerprint_image_region(None, image_bytes=_jpeg_bytes(1024, 291))
    assert should_require_full_cover_followup(
        gap_diag={
            "gcd_match_count": 0,
            "recovery_stage": "p106_1",
            "ready_to_auto_import": False,
            "reason": "ambiguous_gcd_non_barcode_candidates",
        },
        primary_region=region,
        recognition_region=region,
        has_full_cover_image=False,
        local_catalog_hit=False,
        p106_exact_barcode_authority=False,
        barcode_decoded=True,
    )


def test_full_cover_image_region_allows_fingerprint_candidates(tmp_path: Path) -> None:
    engine = _engine()
    img = tmp_path / "cover.jpg"
    img.write_bytes(_jpeg_bytes(800, 1200))
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        session.commit()
        item = IntakeSessionItem(session_id=1, user_id=1, storage_path="x.jpg", status=ITEM_QUEUED)
        hints = gather_intake_gcd_recovery_hints(
            session,
            item=item,
            normalized_barcode=MARVEL_BC,
            image_path=img,
            image_bytes=img.read_bytes(),
            p105=None,
        )
        assert hints.fingerprint_region_safe is True


def test_barcode_strip_worker_ends_needs_full_cover_photo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda *a, **k: None)
    img = _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(900, 280))

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        intake = IntakeSession(
            user_id=1,
            session_token="tok",
            status="active",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(
            session_id=int(intake.id),
            user_id=1,
            storage_path=str(img.name),
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()
        final = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert final == ITEM_NEEDS_FULL_COVER_PHOTO
        assert item.reason == FULL_COVER_USER_MESSAGE
        rows = list(session.exec(select(IntakeItemCandidate).where(IntakeItemCandidate.item_id == item.id)))
        assert rows == []


def test_worker_debug_bundle_written_for_strip_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from app.services.intake_p106_1_intake_debug_service import p106_1_intake_debug_dir

    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda *a, **k: None)
    img = _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(1024, 291))
    debug_item_id = 759606

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        intake = IntakeSession(
            user_id=1,
            session_token="tok-debug",
            status="active",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(
            id=debug_item_id,
            session_id=int(intake.id),
            user_id=1,
            storage_path=str(img.name),
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()
        worker.process_intake_item(session, item_id=debug_item_id)

    debug_dir = p106_1_intake_debug_dir(intake_item_id=debug_item_id)
    region_json = debug_dir / "region_debug.json"
    assert region_json.is_file(), f"missing {region_json}"
    meta = json.loads(region_json.read_text(encoding="utf-8"))
    assert meta["fingerprint_image_region"] == REGION_BARCODE_STRIP
    assert meta["fingerprint_region_safe"] is False
    assert meta["fingerprint_suppressed_reason"]
    assert meta["full_cover_followup_required"] is True
    assert (debug_dir / "recognition_image.jpg").is_file()
    assert (debug_dir / "input.jpg").is_file()
    print(f"DEBUG_DIR={debug_dir}")
    print(f"REGION_JSON={region_json}")


def test_full_cover_followup_reprocess_can_surface_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After attaching a full-cover image, fingerprint hits may appear in diagnosis."""
    import json

    from app.services.intake_full_cover_followup_service import full_cover_storage_path_for_primary

    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda *a, **k: None)
    strip = _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(900, 280))
    full = tmp_path / "full.jpg"
    full.write_bytes(_jpeg_bytes(800, 1200))
    full_dest = full_cover_storage_path_for_primary(strip)
    full_dest.write_bytes(full.read_bytes())

    paths_seen: list[Path] = []

    def _resolve(rel, **k):
        rel_s = str(rel)
        if "fullcover" in rel_s or rel_s == full_dest.name:
            return full_dest
        return strip

    monkeypatch.setattr(worker, "resolve_photo_import_storage_path", _resolve)
    monkeypatch.setattr(
        "app.services.intake_full_cover_followup_service.resolve_photo_import_storage_path",
        _resolve,
    )
    monkeypatch.setattr(
        "app.services.photo_import_storage_service.resolve_photo_import_storage_path",
        _resolve,
    )

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        session.commit()
        intake = IntakeSession(
            user_id=1,
            session_token="tok2",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        payload = {"full_cover_storage_path": str(full_dest.name)}
        item = IntakeSessionItem(
            session_id=int(intake.id),
            user_id=1,
            storage_path=str(strip.name),
            normalized_barcode=MARVEL_BC,
            barcode_read_json=json.dumps(payload),
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()

        fp_called: list[bool] = []

        def _fake_search(session, *, crop_path, limit=5):
            fp_called.append(True)
            return []

        monkeypatch.setattr(
            "app.services.photo_import_fingerprint_service.search_catalog_fingerprint_hits_for_crop_path",
            _fake_search,
        )
        worker.process_intake_item(session, item_id=int(item.id))
        assert fp_called, "fingerprint search should run on full-cover path"


def test_successful_local_barcode_still_auto_matched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc

    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(800, 1200))
    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
        pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
        session.add(pub)
        session.commit()
        series = CatalogSeries(name="X", normalized_name="x", publisher_id=int(pub.id))
        session.add(series)
        session.commit()
        issue = CatalogIssue(
            series_id=int(series.id),
            publisher_id=int(pub.id),
            issue_number="1",
            normalized_issue_number="1",
        )
        session.add(issue)
        session.commit()
        session.add(
            CatalogUpc(upc=MARVEL_BC, normalized_upc=MARVEL_BC, issue_id=int(issue.id), source="test")
        )
        session.commit()
        intake = IntakeSession(
            user_id=1,
            session_token="tok3",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(
            session_id=int(intake.id),
            user_id=1,
            storage_path="scan.jpg",
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()
        final = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert final in {ITEM_AUTO_MATCHED, worker.ITEM_READY_FOR_REVIEW}
        assert final != ITEM_NEEDS_FULL_COVER_PHOTO
